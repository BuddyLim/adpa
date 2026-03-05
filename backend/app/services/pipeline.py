import json

import logfire

from app.agents.coordinator import CoordinatorDeps, coordinator_agent
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import MessageType


async def run_pipeline(
    task_id: str,
    query: str,
    pipeline_run_id: str,
    conversation_id: str,
    pipeline_repo: PipelineRepository,
):
    logfire.info("pipeline started", task_id=task_id)

    try:
        await pipeline_repo.mark_running(pipeline_run_id)
    except Exception as err:
        logfire.error("failed to mark pipeline running", task_id=task_id, error=str(err), exc_info=True)
        raise

    # Step: analyse query
    step_order = 0
    step_msg = "Analysing your query..."
    yield f"data: {json.dumps({'type': MessageType.STATUS, 'message': step_msg})}\n\n"

    with logfire.span("pipeline step", step_order=step_order, message=step_msg):
        try:
            await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg)
        except Exception as err:
            logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
            raise
    step_order += 1

    with logfire.span("coordinator", task_id=task_id, query=query):
        try:
            plan = await coordinator_agent.run(query, deps=CoordinatorDeps(pipeline_repo))
        except Exception as err:
            logfire.error("coordinator agent failed", task_id=task_id, error=str(err), exc_info=True)
            raise

    decision = plan.output
    logfire.info(
        "coordinator decision",
        task_id=task_id,
        accepted=decision.accepted,
        reason=decision.reason,
        datasets=[ds.title for ds in decision.dataset_selected] if decision.dataset_selected else [],
    )

    if not decision.accepted:
        logfire.info("pipeline rejected", task_id=task_id, reason=decision.reason)
        yield f"data: {json.dumps({'type': MessageType.RESULT, 'accepted': decision.accepted, 'reason': decision.reason, 'refined_query': decision.enhanced_query})}\n\n"
        with logfire.span("persist rejection", task_id=task_id):
            try:
                await pipeline_repo.complete_run(pipeline_run_id, decision)
                await pipeline_repo.add_assistant_message(conversation_id, decision.reason)
            except Exception as err:
                logfire.error("failed to persist rejection", task_id=task_id, error=str(err), exc_info=True)
                raise
        return

    if not decision.dataset_selected:
        logfire.warn("no dataset selected", task_id=task_id)
        no_dataset_reason = "Could not find relevant dataset"
        yield f"data: {json.dumps({'type': MessageType.RESULT, 'accepted': False, 'reason': no_dataset_reason, 'refined_query': decision.enhanced_query})}\n\n"
        with logfire.span("persist no-dataset result", task_id=task_id):
            try:
                await pipeline_repo.complete_run(pipeline_run_id, decision)
                await pipeline_repo.add_assistant_message(conversation_id, no_dataset_reason)
            except Exception as err:
                logfire.error("failed to persist no-dataset result", task_id=task_id, error=str(err), exc_info=True)
                raise
        return

    # Step: dataset found
    dataset_titles = [ds.title for ds in decision.dataset_selected]
    step_msg = f"Dataset found - Using: {dataset_titles}"
    logfire.info("dataset selected", task_id=task_id, datasets=dataset_titles)
    yield f"data: {json.dumps({'type': MessageType.STATUS, 'message': step_msg})}\n\n"

    with logfire.span("pipeline step", step_order=step_order, message=step_msg):
        try:
            await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg)
        except Exception as err:
            logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
            raise

    yield f"data: {json.dumps({'type': MessageType.RESULT, 'accepted': decision.accepted, 'reason': decision.reason, 'refined_query': decision.enhanced_query})}\n\n"

    with logfire.span("persist result", task_id=task_id, datasets=dataset_titles):
        try:
            await pipeline_repo.complete_run(pipeline_run_id, decision)
            await pipeline_repo.add_assistant_message(conversation_id, decision.reason)
        except Exception as err:
            logfire.error("failed to persist result", task_id=task_id, error=str(err), exc_info=True)
            raise

    logfire.info("pipeline completed", task_id=task_id)

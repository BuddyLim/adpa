import logfire

from app.agents.analysis import stream_narrative
from app.agents.coordinator_graph import run_coordinator_graph
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import AnalysisTextEvent, CoordinatorDecision, ErrorEvent, ResultEvent


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

    decision: CoordinatorDecision | None = None
    with logfire.span("coordinator graph", task_id=task_id, query=query):
        try:
            async for item in run_coordinator_graph(
                query=query,
                pipeline_run_id=pipeline_run_id,
                conversation_id=conversation_id,
                pipeline_repo=pipeline_repo,
            ):
                if isinstance(item, str):
                    yield item  # SSE event — streamed in real-time as each node completes
                else:
                    decision = item  # CoordinatorDecision — always the last item
        except Exception as err:
            logfire.error("coordinator graph failed", task_id=task_id, error=str(err), exc_info=True)
            try:
                await pipeline_repo.fail_run(pipeline_run_id, "coordinator", str(err))
            except Exception:
                pass
            raise

    if decision is None:
        logfire.error("coordinator graph yielded no decision", task_id=task_id)
        yield f"data: {ErrorEvent(message='Internal error: pipeline produced no result.').model_dump_json()}\n\n"
        return

    if not decision.accepted:
        logfire.info("pipeline rejected", task_id=task_id, reason=decision.reason)
        yield f"data: {ResultEvent(accepted=False, reason=decision.reason, refined_query=decision.enhanced_query).model_dump_json()}\n\n"
        try:
            await pipeline_repo.complete_run(pipeline_run_id, decision)
            await pipeline_repo.add_assistant_message(conversation_id, decision.reason)
        except Exception as err:
            logfire.error("failed to persist rejection", task_id=task_id, error=str(err), exc_info=True)
            raise
        return

    if decision.analysis_result is None:
        logfire.error("accepted decision missing analysis_result", task_id=task_id)
        yield f"data: {ErrorEvent(message='Internal error: analysis result unavailable.').model_dump_json()}\n\n"
        return

    # Stream narrative and accumulate for persistence
    narrative_chunks: list[str] = []
    async for chunk in stream_narrative(decision.analysis_result, decision.enhanced_query):
        narrative_chunks.append(chunk)
        yield f"data: {AnalysisTextEvent(chunk=chunk).model_dump_json()}\n\n"
    narrative_text = "".join(narrative_chunks)

    with logfire.span("persist result", task_id=task_id):
        try:
            await pipeline_repo.complete_run(pipeline_run_id, decision)
            await pipeline_repo.add_assistant_message(conversation_id, narrative_text)
        except Exception as err:
            logfire.error("failed to persist result", task_id=task_id, error=str(err), exc_info=True)
            raise

    yield f"data: {ResultEvent(accepted=decision.accepted, reason=decision.reason, refined_query=decision.enhanced_query).model_dump_json()}\n\n"

    logfire.info("pipeline completed", task_id=task_id)

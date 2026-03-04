import json

import logfire

from app.agents.coordinator import coordinator_agent
from app.schemas.query import MessageType


async def run_pipeline(task_id: str, query: str):
    logfire.info("Pipeline started", task_id=task_id, query=query)

    yield f"data: {json.dumps({'type': MessageType.STATUS, 'message': 'Analysing your query...'})}\n\n"

    with logfire.span("coordinator", task_id=task_id):
        plan = await coordinator_agent.run(query)

    decision = plan.output
    logfire.info(
        "Coordinator decision",
        task_id=task_id,
        accepted=decision.accepted,
        reason=decision.reason,
        dataset=decision.dataset_selected.title if decision.dataset_selected else None,
    )

    if not decision.accepted:
        logfire.info("Pipeline rejected", task_id=task_id, reason=decision.reason)
        yield f"""data: {
            json.dumps(
                {
                    "type": MessageType.RESULT,
                    "accepted": decision.accepted,
                    "reason": decision.reason,
                    "refined_query": decision.refined_query,
                }
            )
        }\n\n"""

        return
    if not decision.dataset_selected:
        logfire.warn("No dataset selected", task_id=task_id)
        yield f"""data: {
            json.dumps(
                {
                    "type": MessageType.RESULT,
                    "accepted": False,
                    "reason": "Could not find relevant dataset",
                    "refined_query": decision.refined_query,
                }
            )
        }\n\n"""

        return

    logfire.info(
        "Dataset selected",
        task_id=task_id,
        dataset_title=decision.dataset_selected.title,
        dataset_path=decision.dataset_selected.path,
    )
    yield f"data: {json.dumps({'type': MessageType.STATUS, 'message': f'Dataset found - Using: {decision.dataset_selected.title}'})}\n\n"

    yield f"""data: {
        json.dumps(
            {
                "type": MessageType.RESULT,
                "accepted": decision.accepted,
                "reason": decision.reason,
                "refined_query": decision.refined_query,
            }
        )
    }\n\n"""

    logfire.info("Pipeline completed", task_id=task_id)

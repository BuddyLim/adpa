import asyncio
from typing import AsyncGenerator

from pydantic_graph import Graph

from app.agents.coordinator_nodes import (
    AnalyzeIntentNode,
    AnalyzeNode,
    ExtractNode,
    LoadContextNode,
    NormalizeNode,
    PlanResearchNode,
    SelectDatasetsNode,
    ValidateAnalysisNode,
    ValidateDatasetPlanNode,
)
from app.agents.coordinator_state import CoordinatorGraphDeps, CoordinatorState
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import CoordinatorDecision


# ─── Graph assembly ───────────────────────────────────────────────────────────

coordinator_graph = Graph(
    nodes=[
        LoadContextNode,
        AnalyzeIntentNode,
        SelectDatasetsNode,
        ValidateDatasetPlanNode,
        PlanResearchNode,
        ExtractNode,
        NormalizeNode,
        AnalyzeNode,
        ValidateAnalysisNode,
    ]
)


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_coordinator_graph(
    query: str,
    pipeline_run_id: str,
    conversation_id: str,
    pipeline_repo: PipelineRepository,
) -> AsyncGenerator[str | CoordinatorDecision, None]:
    """
    Run the full coordinator graph, yielding SSE event strings in real-time.
    The final item yielded is the CoordinatorDecision.

    The graph runs as a background task; events are streamed via an asyncio.Queue
    so the frontend sees each StatusEvent / ToolCallEvent / ToolResultEvent the
    moment a node emits it, not after the node has finished.
    """
    state = CoordinatorState(
        raw_query=query,
        conversation_id=conversation_id,
        pipeline_run_id=pipeline_run_id,
    )
    deps = CoordinatorGraphDeps(
        pipeline_repo=pipeline_repo,
        pipeline_run_id=pipeline_run_id,
    )

    # Mutable holder so the closure can pass the final decision back out
    result_holder: list[CoordinatorDecision] = []

    async def _run_graph() -> None:
        try:
            async with coordinator_graph.iter(
                LoadContextNode(), state=state, deps=deps
            ) as graph_run:
                async for _ in graph_run:
                    pass
            if graph_run.result is None:
                raise RuntimeError("Coordinator graph completed without a result")
            result_holder.append(graph_run.result.output)
        finally:
            # Always unblock the consumer, even on error
            await state.sse_queue.put(None)

    graph_task = asyncio.create_task(_run_graph())

    # Consume events in real-time; None sentinel signals graph completion
    while True:
        item = await state.sse_queue.get()
        if item is None:
            break
        yield item

    await graph_task  # re-raise any exception from the graph

    if not result_holder:
        raise RuntimeError("Coordinator graph completed without a result")
    yield result_holder[0]

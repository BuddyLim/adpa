import asyncio
import json

import logfire
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

from app.agents.analysis import run_analysis, stream_narrative
from app.agents.coordinator import CoordinatorDeps, coordinator_agent
from app.agents.extraction import ExtractionDeps, PeerSchema, extraction_agent, load_schema
from app.agents.normalization import run_normalization
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import AnalysisTextEvent, MessageType, NormalizationResult, ResultEvent, ToolCallEvent, ToolResultEvent


def _build_tool_events(messages: list, agent_name: str) -> list[ToolCallEvent | ToolResultEvent]:
    """Extract tool_call / tool_result SSE events from a completed agent run's messages."""
    events: list[ToolCallEvent | ToolResultEvent] = []

    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    elif not isinstance(args, dict):
                        args = {}
                    events.append(ToolCallEvent(
                        tool=f"{agent_name}/{part.tool_name}",
                        args=args,
                    ))
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    try:
                        result_val = json.loads(part.content)
                    except (json.JSONDecodeError, TypeError):
                        result_val = str(part.content)
                    events.append(ToolResultEvent(
                        tool=f"{agent_name}/{part.tool_name}",
                        result=result_val,
                    ))

    return events



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
            await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg, step_type="query_analysis")
        except Exception as err:
            logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
            raise
    step_order += 1

    with logfire.span("coordinator", task_id=task_id, query=query):
        try:
            plan = await coordinator_agent.run(query, deps=CoordinatorDeps(pipeline_repo))
        except Exception as err:
            logfire.error("coordinator agent failed", task_id=task_id, error=str(err), exc_info=True)
            try:
                await pipeline_repo.fail_run(pipeline_run_id, "coordinator", str(err))
            except Exception:
                pass
            raise


    decision = plan.output
    # Emit dataset selection event
    if decision.dataset_selected:
        selected_titles = [ds.title for ds in decision.dataset_selected]
        yield f"data: {ToolCallEvent(tool='coordinator/datasets_selected', args={}).model_dump_json()}\n\n"
        yield f"data: {ToolResultEvent(tool='coordinator/datasets_selected', result={'datasets': selected_titles}).model_dump_json()}\n\n"

    logfire.info(
        "coordinator decision",
        task_id=task_id,
        accepted=decision.accepted,
        reason=decision.reason,
        datasets=[ds.title for ds in decision.dataset_selected] if decision.dataset_selected else [],
    )

    if not decision.accepted:
        logfire.info("pipeline rejected", task_id=task_id, reason=decision.reason)
        yield f"data: {ResultEvent(accepted=decision.accepted, reason=decision.reason, refined_query=decision.enhanced_query).model_dump_json()}\n\n"
        with logfire.span("persist rejection", task_id=task_id):
            try:
                await pipeline_repo.complete_run(pipeline_run_id, decision)
                await pipeline_repo.add_assistant_message(conversation_id, decision.reason)
            except Exception as err:
                logfire.error("failed to persist rejection", task_id=task_id, error=str(err), exc_info=True)
                raise
        return

    # Emit coordinator tool events
    for event in _build_tool_events(plan.all_messages(), "coordinator"):
        yield f"data: {event.model_dump_json()}\n\n"


    if not decision.dataset_selected:
        logfire.warn("no dataset selected", task_id=task_id)
        no_dataset_reason = "Could not find relevant dataset"
        yield f"data: {ResultEvent(accepted=False, reason=no_dataset_reason, refined_query=decision.enhanced_query).model_dump_json()}\n\n"
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
    step_msg = f"Dataset(s) found: {dataset_titles}"
    logfire.info("dataset selected", task_id=task_id, datasets=dataset_titles)

    with logfire.span("pipeline step", step_order=step_order, message=step_msg):
        try:
            await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg, step_type="dataset_found")
        except Exception as err:
            logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
            raise

    # Ensure Dataset rows exist before extraction so extraction_results.dataset_id can be populated
    with logfire.span("ensure datasets", task_id=task_id):
        try:
            dataset_ids = await pipeline_repo.ensure_datasets(decision.dataset_selected)
        except Exception as err:
            logfire.error("failed to ensure datasets", task_id=task_id, error=str(err), exc_info=True)
            try:
                await pipeline_repo.fail_run(pipeline_run_id, "ensure_datasets", str(err))
            except Exception:
                pass
            raise

    # Fetch prior conversation turns (exclude the current user message — last item)
    all_messages = await pipeline_repo.get_messages(conversation_id)
    conversation_history = all_messages[:-1] if all_messages else []

    # Load all dataset schemas upfront so each extraction agent can see its peers
    all_schemas: list[PeerSchema] = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: [load_schema(ds.path, ds.title) for ds in decision.dataset_selected] # type: ignore
    )

    async def extraction_task(path: str, title: str, ref: int):
        with logfire.span(f"extraction #{ref}", task_id=task_id, query=decision.enhanced_query, title=title):
            try:
                peer_schemas = [s for s in all_schemas if s.title != title]

                history_text = ""
                if conversation_history:
                    history_text = (
                        "Prior conversation context:\n"
                        + "\n".join(
                            f"{m['role'].upper()}: {m['content']}"
                            for m in conversation_history
                        )
                        + "\n\n"
                    )

                peer_text = ""
                if peer_schemas:
                    peer_text = "Peer datasets being extracted in parallel:\n"
                    for peer in peer_schemas:
                        cols = ", ".join(f"{c['name']} ({c['type']})" for c in peer.columns)
                        peer_text += f"- {peer.title}: {cols}\n"
                    peer_text += (
                        "\nAlign your column selection and join_keys with the above so that "
                        "the normalization step can merge results without guessing mappings.\n\n"
                    )

                with ExtractionDeps(
                    dataset_path=path,
                    dataset_title=title,
                    peer_schemas=peer_schemas,
                    conversation_history=conversation_history,
                ) as deps:
                    result = await extraction_agent.run(
                        f"""
                        {history_text}

                        {peer_text}

                        Extract data relevant to this query: {decision.enhanced_query}""",
                        deps=deps,
                    )
                return result
            except Exception as err:
                logfire.error("extraction agent failed", task_id=task_id, title=title, error=str(err), exc_info=True)
                try:
                    await pipeline_repo.fail_run(pipeline_run_id, "extraction", str(err))
                except Exception:
                    pass
                raise

    # Emit a single extraction start event
    yield f"data: {ToolCallEvent(tool='pipeline/extraction', args={'datasets': dataset_titles}).model_dump_json()}\n\n"

    task_list = [
        asyncio.create_task(extraction_task(ds.path, ds.title, i))
        for i, ds in enumerate(decision.dataset_selected)
    ]
    extraction_runs = await asyncio.gather(*task_list)
    extraction_results = [r.output for r in extraction_runs]
    logfire.info("extraction complete", task_id=task_id, n_datasets=len(extraction_results))

    # Emit a single extraction result event
    total_rows = sum(len(r.rows) for r in extraction_results)
    yield f"data: {ToolResultEvent(tool='pipeline/extraction', result={'datasets': [{'title': r.source_dataset, 'row_count': len(r.rows)} for r in extraction_results], 'total_rows': total_rows}).model_dump_json()}\n\n"

    with logfire.span("persist extraction results", task_id=task_id):
        try:
            await pipeline_repo.save_extraction_results(pipeline_run_id, extraction_results, dataset_ids)
        except Exception as err:
            logfire.error("failed to persist extraction results", task_id=task_id, error=str(err), exc_info=True)
            raise
    
    if len(extraction_results) > 1:
        # Step: normalize
        step_order += 1
        step_msg = "Normalizing data across sources..."

        with logfire.span("pipeline step", step_order=step_order, message=step_msg):
            try:
                await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg, step_type="normalization")
            except Exception as err:
                logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
                raise

        # Emit a single normalization start event
        yield f"data: {ToolCallEvent(tool='pipeline/normalization', args={'n_sources': len(extraction_results), 'datasets': dataset_titles}).model_dump_json()}\n\n"

        with logfire.span("normalization", task_id=task_id):
            try:
                normalization_result, _ = await run_normalization(extraction_results, decision.enhanced_query)
            except Exception as err:
                logfire.error("normalization agent failed", task_id=task_id, error=str(err), exc_info=True)
                try:
                    await pipeline_repo.fail_run(pipeline_run_id, "normalization", str(err))
                except Exception:
                    pass
                raise

        # Emit a single normalization result event
        yield f"data: {ToolResultEvent(tool='pipeline/normalization', result={'unified_rows': len(normalization_result.unified_rows), 'columns': normalization_result.columns}).model_dump_json()}\n\n"
    else:
        # Single dataset — skip normalization agent, map directly
        er = extraction_results[0]
        columns = list(er.rows[0].keys()) if er.rows else []
        normalization_result = NormalizationResult(
            notes="Single dataset — normalization skipped.",
            unified_rows=er.rows,
            columns=columns,
        )

    with logfire.span("persist normalization result", task_id=task_id):
        try:
            await pipeline_repo.save_normalization_result(pipeline_run_id, normalization_result)
        except Exception as err:
            logfire.error("failed to persist normalization result", task_id=task_id, error=str(err), exc_info=True)
            raise

    # Step: analysis
    step_order += 1
    step_msg = "Analysing data and generating insights..."
    yield f"data: {json.dumps({'type': MessageType.STATUS, 'message': step_msg})}\n\n"

    with logfire.span("pipeline step", step_order=step_order, message=step_msg):
        try:
            await pipeline_repo.add_step(pipeline_run_id, order=step_order, message=step_msg, step_type="analysis")
        except Exception as err:
            logfire.error("failed to persist pipeline step", task_id=task_id, step_order=step_order, error=str(err), exc_info=True)
            raise

    yield f"data: {ToolCallEvent(tool='pipeline/analysis', args={'unified_rows': len(normalization_result.unified_rows), 'columns': normalization_result.columns}).model_dump_json()}\n\n"

    with logfire.span("analysis", task_id=task_id):
        try:
            analysis_result, analysis_messages = await run_analysis(
                normalization_result, decision.enhanced_query
            )
        except Exception as err:
            logfire.error("analysis agent failed", task_id=task_id, error=str(err), exc_info=True)
            try:
                await pipeline_repo.fail_run(pipeline_run_id, "analysis", str(err))
            except Exception:
                pass
            raise

    yield f"data: {ToolResultEvent(tool='pipeline/analysis', result=analysis_result.model_dump()).model_dump_json()}\n\n"

    # Accumulate narrative so it can be persisted as the assistant message
    narrative_chunks: list[str] = []
    async for chunk in stream_narrative(analysis_result, decision.enhanced_query):
        narrative_chunks.append(chunk)
        yield f"data: {AnalysisTextEvent(chunk=chunk).model_dump_json()}\n\n"
    narrative_text = "".join(narrative_chunks)

    with logfire.span("persist analysis result", task_id=task_id):
        try:
            await pipeline_repo.save_analysis_result(pipeline_run_id, analysis_result)
        except Exception as err:
            logfire.error("failed to persist analysis result", task_id=task_id, error=str(err), exc_info=True)
            raise

    with logfire.span("persist result", task_id=task_id, datasets=dataset_titles):
        try:
            await pipeline_repo.complete_run(pipeline_run_id, decision)
            await pipeline_repo.add_assistant_message(conversation_id, narrative_text)
        except Exception as err:
            logfire.error("failed to persist result", task_id=task_id, error=str(err), exc_info=True)
            raise

    yield f"data: {ResultEvent(accepted=decision.accepted, reason=decision.reason, refined_query=decision.enhanced_query).model_dump_json()}\n\n"

    logfire.info("pipeline completed", task_id=task_id)

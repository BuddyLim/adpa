import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncGenerator, TypeVar, Union

import logfire
from pydantic_ai import Agent
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from app.agents.extraction import ExtractionDeps, PeerSchema, extraction_agent, load_schema
from app.agents.normalization import run_normalization
from app.agents.analysis import run_analysis, validate_analysis
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import (
    AnalysisResult,
    ConversationMessage,
    CoordinatorDataset,
    CoordinatorDecision,
    DatasetInfo,
    DatasetSelectionOutput,
    DatasetValidationOutput,
    ExtractionResult,
    IntentAnalysis,
    NormalizationResult,
    PriorAnalysis,
    ResearchPlan,
    StatusEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from app.services.llm import get_llm_model_with_fallback

_T = TypeVar("_T")


# ─── Graph state ──────────────────────────────────────────────────────────────

@dataclass
class CoordinatorState:
    raw_query: str
    conversation_id: str
    pipeline_run_id: str
    # Loaded by LoadContextNode
    available_datasets: list[DatasetInfo] = field(default_factory=list)
    conversation_history: list[ConversationMessage] = field(default_factory=list)
    prior_datasets_used: list[str] = field(default_factory=list)
    prior_analyses: list[PriorAnalysis] = field(default_factory=list)
    # Coordinator nodes
    intent: IntentAnalysis | None = None
    dataset_selection: DatasetSelectionOutput | None = None
    validation_feedback: str | None = None
    selection_iterations: int = 0
    dataset_ids: dict[str, str] = field(default_factory=dict)
    # Planning node
    research_plan: ResearchPlan | None = None
    # Pipeline nodes
    extraction_results: list[ExtractionResult] = field(default_factory=list)
    normalization_result: NormalizationResult | None = None
    analysis_result: AnalysisResult | None = None
    analysis_iterations: int = 0
    analysis_feedback: str | None = None
    # Root-cause routing (set by ValidateAnalysisNode when routing upstream)
    extraction_feedback: str | None = None  # consumed by PlanResearchNode / SelectDatasetsNode
    pipeline_iterations: int = 0            # counts backward re-entries past AnalyzeNode
    # Step order counter for DB persistence
    step_order: int = 0
    # Queue for real-time SSE event streaming; None sentinel signals completion
    sse_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


# ─── Graph deps ───────────────────────────────────────────────────────────────

@dataclass
class CoordinatorGraphDeps:
    pipeline_repo: PipelineRepository
    pipeline_run_id: str


# ─── Per-node agents ──────────────────────────────────────────────────────────

intent_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a query intent classifier for a government policy data analytics platform.


    Given a user query and optional conversation history, you must:
    1. Determine if this is a follow-up to a prior query (is_followup=true) and if so,
       identify which datasets were previously used (suggested_prior_datasets) so the
       planner can consider re-using them.
    2. Enhance the raw query with domain-specific terminology and analytical framing.
       The enhanced_query should be 2-4 sentences, specific, and mention the type of
       analysis needed (trend, comparison, ranking, distribution, etc.).
    3. Identify the policy domain (e.g. "transport", "demographics", "housing",
       "employment", "health", "education").
    4. Determine feasibility:
       - Reject (is_feasible=false) if: completely off-domain, asking for personal /
         real-time / non-statistical information, or too vague to specify any data
         dimension (e.g. "tell me about Singapore").
       - Accept (is_feasible=true) if: relates to any policy/statistical domain, even
         if you are unsure which dataset covers it.
    5. If rejecting, set rejection_reason to a clear, user-friendly explanation.
    6. If the user specifies a single year, preserve that year constraint in enhanced_query. 
       Only expand to time-series framing if the user explicitly requests a trend across multiple 
       years or a date range
    """,
    output_type=IntentAnalysis,
)

dataset_selector_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a dataset mapping specialist for a government policy analytics platform.

    Given an enhanced analytical query, its policy domain, and a catalogue of available
    datasets, select 1-3 datasets that together can answer the query.

    Rules:
    - Only select datasets whose title/description genuinely overlaps the query domain.
    - If no dataset is relevant, set cannot_answer=true with a clear reason.
    - For each selected dataset include a one-sentence selection_reason.
    - If the query is a follow-up and suggested_prior_datasets are listed, prefer them
      unless there is a compelling reason to switch.
    - For multi-dataset queries ensure the datasets can be joined (shared key columns).
    """,
    output_type=DatasetSelectionOutput,
)

dataset_validator_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a dataset plan validator for a government policy analytics platform.

    Given an enhanced query and a proposed set of datasets, decide whether the selected
    datasets can actually answer the query.

    Validation criteria:
    1. Coverage: do the dataset titles/descriptions suggest they contain the relevant
       data dimensions (time range, geography, metrics, categories)?
    2. Sufficiency: are there enough datasets for comparison/trend queries, or is one
       dataset clearly sufficient?
    3. Relevance: are any selected datasets clearly irrelevant?

    If valid=true, set confirmation_reason (1 sentence).
    If valid=false, set feedback describing what is missing so the selector can improve.
    Do NOT be overly strict - if datasets are plausibly relevant, mark valid=true.
    """,
    output_type=DatasetValidationOutput,
)

research_planner_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a research strategist for a government policy analytics platform.

    Given an enhanced analytical query, its domain, and the selected datasets, produce
    a structured research plan that guides the downstream extraction and analysis pipeline.

    Your plan must specify:
    1. analysis_type: the primary analysis pattern:
       - "trend": how a metric changes over time
       - "comparison": comparing values across categories, regions, or groups
       - "ranking": identifying top/bottom performers
       - "distribution": understanding spread and concentration of values
       - "correlation": relationship between two or more metrics
    2. sub_questions: 2-4 specific analytical questions that, answered together, fully
       address the user's query. Be concrete - reference specific dimensions where possible.
    3. key_metrics: the specific columns or computed metrics to prioritise. Use descriptive
       names even if the exact column name is unknown.
    4. extraction_hints: per-dataset instructions keyed by dataset title. For each dataset,
       provide a one-sentence instruction specifying relevant columns, filters, time ranges,
       or categories to include.
    5. suggested_chart_types: 2-3 chart types that best represent the analysis_type
       (bar, line, area, pie).
    """,
    output_type=ResearchPlan,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _require(value: _T | None, field: str) -> _T:
    """Narrow an optional state field to its non-None type.

    Raises RuntimeError if None, which indicates a node ordering bug — a
    later node ran before the earlier node that was supposed to set this field.
    """
    if value is None:
        raise RuntimeError(f"Coordinator state invariant violated: '{field}' is None")
    return value


def _format_conversation_for_prompt(
    history: list[ConversationMessage],
    prior_datasets_used: list[str],
    prior_analyses: list[PriorAnalysis],
) -> str:
    if not history and not prior_datasets_used and not prior_analyses:
        return ""

    lines = ["=== Conversation History ==="]
    for msg in history:
        lines.append(f"{msg.role.upper()}: {msg.content}")

    if prior_analyses:
        lines.append("")
        lines.append("Prior pipeline runs (structured analysis results):")
        for i, pa in enumerate(prior_analyses, 1):
            lines.append(f"Run {i} - Query: \"{pa.enhanced_query}\"")
            if pa.summary:
                lines.append(f"  Summary: {pa.summary}")
            for kf in pa.key_findings:
                lines.append(f"  - {kf}")
    elif prior_datasets_used:
        lines.append("")
        lines.append(f"Datasets used in prior pipeline runs: {', '.join(prior_datasets_used)}")

    lines.append("=== End History ===")
    return "\n".join(lines)


def _append_sse(state: CoordinatorState, event: ToolCallEvent | ToolResultEvent | StatusEvent) -> None:
    state.sse_queue.put_nowait(f"data: {event.model_dump_json()}\n\n")


def _rejection_end(reason: str, enhanced_query: str) -> "End[CoordinatorDecision]":
    return End(CoordinatorDecision(
        accepted=False,
        reason=reason,
        enhanced_query=enhanced_query,
        dataset_selected=None,
        analysis_result=None,
    ))


# ─── Global pipeline guard ────────────────────────────────────────────────────

MAX_PIPELINE_ITERATIONS = 2  # max backward re-entries from ValidateAnalysisNode to SelectDatasetsNode or PlanResearchNode


# ─── Graph nodes ──────────────────────────────────────────────────────────────

@dataclass
class LoadContextNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Load datasets, conversation history and prior analysis results from DB."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> "AnalyzeIntentNode":
        repo = ctx.deps.pipeline_repo

        raw_datasets = json.loads(await repo.list_datasets())
        ctx.state.available_datasets = [DatasetInfo.model_validate(d) for d in raw_datasets]

        raw_messages = await repo.get_messages(ctx.state.conversation_id)
        ctx.state.conversation_history = [
            ConversationMessage.model_validate(m) for m in (raw_messages[:-1] if raw_messages else [])
        ]

        prior_runs = await repo.get_conversation_results(ctx.state.conversation_id)
        ctx.state.prior_datasets_used = [
            ds.title
            for run in prior_runs
            if run.status == "completed"
            for ds in (run.datasets or [])
        ]
        ctx.state.prior_analyses = [
            PriorAnalysis(
                enhanced_query=run.enhanced_query,
                summary=run.analysis_result.summary,
                key_findings=run.analysis_result.key_findings,
            )
            for run in prior_runs
            if run.status == "completed" and run.analysis_result and run.enhanced_query
        ]

        logfire.info(
            "coordinator graph: context loaded",
            n_datasets=len(ctx.state.available_datasets),
            n_history_turns=len(ctx.state.conversation_history),
            n_prior_runs=len(prior_runs),
        )
        return AnalyzeIntentNode()


@dataclass
class AnalyzeIntentNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Classify intent, detect follow-ups, enhance query, gate on feasibility."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union["SelectDatasetsNode", End[CoordinatorDecision]]:
        step_msg = "Analysing your query..."
        _append_sse(ctx.state, StatusEvent(message=step_msg))
        await ctx.deps.pipeline_repo.add_step(
            ctx.deps.pipeline_run_id,
            order=ctx.state.step_order,
            message=step_msg,
            step_type="query_analysis",
        )
        ctx.state.step_order += 1

        history_block = _format_conversation_for_prompt(
            ctx.state.conversation_history,
            ctx.state.prior_datasets_used,
            ctx.state.prior_analyses,
        )
        prompt = (
            f"{history_block}\n\n" if history_block else ""
        ) + f"Current query: {ctx.state.raw_query}"

        _append_sse(ctx.state, ToolCallEvent(
            tool="coordinator/analyze_intent",
            args={"query": ctx.state.raw_query},
        ))

        with logfire.span("coordinator graph: analyze intent", query=ctx.state.raw_query):
            result = await intent_agent.run(prompt)

        ctx.state.intent = result.output
        logfire.info(
            "intent analyzed",
            is_feasible=result.output.is_feasible,
            is_followup=result.output.is_followup,
            domain=result.output.domain,
        )

        _append_sse(ctx.state, ToolResultEvent(
            tool="coordinator/analyze_intent",
            result={
                "enhanced_query": result.output.enhanced_query,
                "is_followup": result.output.is_followup,
                "domain": result.output.domain,
            },
        ))

        if not result.output.is_feasible:
            logfire.info("coordinator graph: rejected at intent stage", reason=result.output.rejection_reason)
            return _rejection_end(
                result.output.rejection_reason or "Query is not answerable with available data.",
                result.output.enhanced_query,
            )

        return SelectDatasetsNode()


@dataclass
class SelectDatasetsNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Map intent to datasets; receives validation_feedback on retry iterations."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> "ValidateDatasetPlanNode":
        intent = _require(ctx.state.intent, "intent")
        datasets_block = json.dumps([ds.model_dump() for ds in ctx.state.available_datasets], indent=2)

        feedback_block = ""
        if ctx.state.validation_feedback:
            feedback_block = (
                f"\n\nPREVIOUS SELECTION FAILED VALIDATION:\n{ctx.state.validation_feedback}\n"
                "Please select different or additional datasets that address these gaps."
            )

        analysis_feedback_block = ""
        if ctx.state.extraction_feedback and not ctx.state.validation_feedback:
            # Re-entered from ValidateAnalysisNode (wrong_datasets) — datasets were wrong at analysis stage
            analysis_feedback_block = (
                f"\n\nANALYSIS-STAGE FEEDBACK — previously selected datasets produced wrong metrics:\n"
                f"{ctx.state.extraction_feedback}\n"
                "Select completely different datasets that contain the metric types described above."
            )

        prior_block = ""
        if intent.suggested_prior_datasets:
            prior_block = (
                f"\nNote: prior runs used these datasets: "
                f"{', '.join(intent.suggested_prior_datasets)}. "
                "Consider re-using them if the query is a follow-up.\n"
            )

        prompt = (
            f"Enhanced query: {intent.enhanced_query}\n"
            f"Query domain: {intent.domain}\n"
            f"{prior_block}"
            f"{feedback_block}"
            f"{analysis_feedback_block}\n\n"
            f"Available datasets:\n{datasets_block}"
        )

        _append_sse(ctx.state, ToolCallEvent(
            tool="coordinator/select_datasets",
            args={"domain": intent.domain, "iteration": ctx.state.selection_iterations},
        ))

        with logfire.span("coordinator graph: select datasets", iteration=ctx.state.selection_iterations):
            result = await dataset_selector_agent.run(prompt)

        ctx.state.dataset_selection = result.output
        ctx.state.selection_iterations += 1

        logfire.info(
            "datasets selected",
            n_selected=len(result.output.selected_datasets),
            cannot_answer=result.output.cannot_answer,
        )

        _append_sse(ctx.state, ToolResultEvent(
            tool="coordinator/select_datasets",
            result={
                "selected": [ds.title for ds in result.output.selected_datasets],
                "iteration": ctx.state.selection_iterations,
            },
        ))

        return ValidateDatasetPlanNode()


@dataclass
class ValidateDatasetPlanNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Validate selected datasets; loop back to SelectDatasetsNode on failure."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union["SelectDatasetsNode", "PlanResearchNode", End[CoordinatorDecision]]:
        intent = _require(ctx.state.intent, "intent")
        selection = _require(ctx.state.dataset_selection, "dataset_selection")

        if selection.cannot_answer or not selection.selected_datasets:
            reason = selection.reason or "No relevant datasets found."
            logfire.info("coordinator graph: selector reports cannot answer", reason=reason)
            return _rejection_end(reason, intent.enhanced_query)

        selected_info = json.dumps([
            {"title": ds.title, "path": ds.path, "reason": ds.selection_reason}
            for ds in selection.selected_datasets
        ], indent=2)
        available_info = json.dumps([ds.model_dump() for ds in ctx.state.available_datasets], indent=2)
        prompt = (
            f"Enhanced query: {intent.enhanced_query}\n\n"
            f"Proposed dataset selection:\n{selected_info}\n\n"
            f"Full dataset catalogue (for context):\n{available_info}"
        )

        _append_sse(ctx.state, ToolCallEvent(
            tool="coordinator/validate_plan",
            args={"iteration": ctx.state.selection_iterations},
        ))

        with logfire.span("coordinator graph: validate plan", iteration=ctx.state.selection_iterations):
            result = await dataset_validator_agent.run(prompt)

        validation = result.output

        _append_sse(ctx.state, ToolResultEvent(
            tool="coordinator/validate_plan",
            result={"valid": validation.valid, "feedback": validation.feedback or None},
        ))

        if validation.valid:
            logfire.info("dataset plan validated", n_datasets=len(selection.selected_datasets))

            dataset_titles = [ds.title for ds in selection.selected_datasets]
            step_msg = f"Dataset(s) found: {dataset_titles}"
            _append_sse(ctx.state, StatusEvent(message="Dataset(s) found"))

            coordinator_datasets = [
                CoordinatorDataset(title=ds.title, path=ds.path)
                for ds in selection.selected_datasets
            ]
            ctx.state.dataset_ids = await ctx.deps.pipeline_repo.ensure_datasets(coordinator_datasets)
            await ctx.deps.pipeline_repo.add_step(
                ctx.deps.pipeline_run_id,
                order=ctx.state.step_order,
                message=step_msg,
                step_type="dataset_found",
            )
            ctx.state.step_order += 1

            _append_sse(ctx.state, ToolCallEvent(tool="coordinator/datasets_selected", args={}))
            _append_sse(ctx.state, ToolResultEvent(
                tool="coordinator/datasets_selected",
                result={"datasets": dataset_titles},
            ))

            return PlanResearchNode()

        if ctx.state.selection_iterations < 2:
            logfire.info(
                "dataset plan failed validation, retrying",
                iteration=ctx.state.selection_iterations,
                feedback=validation.feedback,
            )
            ctx.state.validation_feedback = validation.feedback
            return SelectDatasetsNode()

        logfire.warn("dataset plan exhausted retries", iteration=ctx.state.selection_iterations)
        return _rejection_end(
            f"Could not find datasets that reliably answer the query after "
            f"{ctx.state.selection_iterations} attempts. {validation.feedback}",
            intent.enhanced_query,
        )


@dataclass
class PlanResearchNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Produce a structured research plan guiding extraction and analysis."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> "ExtractNode":
        intent = _require(ctx.state.intent, "intent")
        selection = _require(ctx.state.dataset_selection, "dataset_selection")

        datasets_block = json.dumps([
            {"title": ds.title, "selection_reason": ds.selection_reason}
            for ds in selection.selected_datasets
        ], indent=2)

        extraction_feedback_block = ""
        if ctx.state.extraction_feedback:
            # Re-entered from ValidateAnalysisNode (insufficient_data) — prior extraction was too narrow
            extraction_feedback_block = (
                f"\n\nEXTRACTION FEEDBACK — previous extraction was insufficient:\n"
                f"{ctx.state.extraction_feedback}\n"
                "Update extraction_hints to be more specific: broader date ranges, additional "
                "relevant columns, relaxed filters, or explicit minimum row requirements."
            )

        prompt = (
            f"Enhanced query: {intent.enhanced_query}\n"
            f"Domain: {intent.domain}\n\n"
            f"Selected datasets:\n{datasets_block}"
            f"{extraction_feedback_block}"
        )

        _append_sse(ctx.state, ToolCallEvent(tool="coordinator/plan_research", args={}))

        with logfire.span("coordinator graph: plan research"):
            result = await research_planner_agent.run(prompt)

        ctx.state.research_plan = result.output
        logfire.info(
            "research plan produced",
            analysis_type=result.output.analysis_type,
            n_sub_questions=len(result.output.sub_questions),
        )

        _append_sse(ctx.state, ToolResultEvent(
            tool="coordinator/plan_research",
            result={
                "analysis_type": result.output.analysis_type,
                "sub_questions": result.output.sub_questions,
                "suggested_chart_types": result.output.suggested_chart_types,
            },
        ))

        return ExtractNode()


@dataclass
class ExtractNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Run extraction agents in parallel for all selected datasets."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union["NormalizeNode", End[CoordinatorDecision]]:
        state = ctx.state
        intent = _require(state.intent, "intent")
        selection = _require(state.dataset_selection, "dataset_selection")
        plan = state.research_plan  # optional — may be None if PlanResearchNode failed gracefully

        dataset_titles = [ds.title for ds in selection.selected_datasets]

        _append_sse(state, ToolCallEvent(
            tool="pipeline/extraction",
            args={"datasets": dataset_titles},
        ))

        all_schemas: list[PeerSchema] = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: [load_schema(ds.path, ds.title) for ds in selection.selected_datasets],
        )

        async def extraction_task(path: str, title: str, ref: int) -> ExtractionResult:
            with logfire.span(f"extraction #{ref}", title=title):
                peer_schemas = [s for s in all_schemas if s.title != title]

                history_text = ""
                if state.conversation_history:
                    history_text = (
                        "Prior conversation context:\n"
                        + "\n".join(
                            f"{m.role.upper()}: {m.content}"
                            for m in state.conversation_history
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

                hint_text = ""
                if plan and title in plan.extraction_hints:
                    hint_text = (
                        f"Extraction guidance for this dataset: {plan.extraction_hints[title]}\n\n"
                    )

                with ExtractionDeps(
                    dataset_path=path,
                    dataset_title=title,
                    peer_schemas=peer_schemas,
                    conversation_history=[m.model_dump() for m in state.conversation_history],
                ) as deps:
                    result = await extraction_agent.run(
                        f"{history_text}{hint_text}{peer_text}"
                        f"Extract data relevant to this query: {intent.enhanced_query}",
                        deps=deps,
                    )
                return result.output

        task_list = [
            asyncio.create_task(extraction_task(ds.path, ds.title, i))
            for i, ds in enumerate(selection.selected_datasets)
        ]

        try:
            extraction_results = list(await asyncio.gather(*task_list))
        except Exception as err:
            logfire.error("extraction failed", error=str(err), exc_info=True)
            await ctx.deps.pipeline_repo.fail_run(ctx.deps.pipeline_run_id, "extraction", str(err))
            return _rejection_end(f"Data extraction failed: {err}", intent.enhanced_query)

        state.extraction_results = extraction_results

        try:
            await ctx.deps.pipeline_repo.save_extraction_results(
                ctx.deps.pipeline_run_id, extraction_results, state.dataset_ids
            )
        except Exception as err:
            logfire.error("failed to persist extraction results", error=str(err), exc_info=True)

        total_rows = sum(len(r.rows) for r in extraction_results)
        logfire.info("extraction complete", n_datasets=len(extraction_results), total_rows=total_rows)

        _append_sse(state, ToolResultEvent(
            tool="pipeline/extraction",
            result={
                "datasets": [{"title": r.source_dataset, "row_count": len(r.rows)} for r in extraction_results],
                "total_rows": total_rows,
            },
        ))

        return NormalizeNode()


@dataclass
class NormalizeNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Normalize extraction results into a unified dataset; skip if single source."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union["AnalyzeNode", End[CoordinatorDecision]]:
        state = ctx.state
        intent = _require(state.intent, "intent")
        extraction_results = state.extraction_results

        if len(extraction_results) > 1:
            step_msg = "Normalizing data across sources..."
            _append_sse(state, StatusEvent(message=step_msg))
            await ctx.deps.pipeline_repo.add_step(
                ctx.deps.pipeline_run_id,
                order=state.step_order,
                message=step_msg,
                step_type="normalization",
            )
            state.step_order += 1

            _append_sse(state, ToolCallEvent(
                tool="pipeline/normalization",
                args={"n_sources": len(extraction_results)},
            ))

            try:
                normalization_result, _ = await run_normalization(
                    extraction_results, intent.enhanced_query
                )
            except Exception as err:
                logfire.error("normalization failed", error=str(err), exc_info=True)
                await ctx.deps.pipeline_repo.fail_run(ctx.deps.pipeline_run_id, "normalization", str(err))
                return _rejection_end(f"Data normalization failed: {err}", intent.enhanced_query)

            _append_sse(state, ToolResultEvent(
                tool="pipeline/normalization",
                result={
                    "unified_rows": len(normalization_result.unified_rows),
                    "columns": normalization_result.columns,
                },
            ))
        else:
            er = extraction_results[0]
            columns = list(er.rows[0].keys()) if er.rows else []
            normalization_result = NormalizationResult(
                notes="Single dataset - normalization skipped.",
                unified_rows=er.rows,
                columns=columns,
            )

        state.normalization_result = normalization_result

        try:
            await ctx.deps.pipeline_repo.save_normalization_result(
                ctx.deps.pipeline_run_id, normalization_result
            )
        except Exception as err:
            logfire.error("failed to persist normalization result", error=str(err), exc_info=True)

        return AnalyzeNode()


@dataclass
class AnalyzeNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Run analysis agent, guided by the research plan."""

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union["ValidateAnalysisNode", End[CoordinatorDecision]]:
        state = ctx.state
        intent = _require(state.intent, "intent")
        normalization_result = _require(state.normalization_result, "normalization_result")

        if state.analysis_iterations == 0:
            step_msg = "Analysing data and generating insights..."
            _append_sse(state, StatusEvent(message=step_msg))
            await ctx.deps.pipeline_repo.add_step(
                ctx.deps.pipeline_run_id,
                order=state.step_order,
                message=step_msg,
                step_type="analysis",
            )
            state.step_order += 1

            _append_sse(state, ToolCallEvent(
                tool="pipeline/analysis",
                args={
                    "unified_rows": len(normalization_result.unified_rows),
                    "columns": normalization_result.columns,
                },
            ))

        try:
            analysis_result, _ = await run_analysis(
                normalization_result,
                intent.enhanced_query,
                feedback=state.analysis_feedback,
                prior_analyses=[pa.model_dump() for pa in state.prior_analyses] if state.analysis_iterations == 0 else None,
                research_plan=state.research_plan,
            )
        except Exception as err:
            logfire.error("analysis failed", iteration=state.analysis_iterations, error=str(err), exc_info=True)
            await ctx.deps.pipeline_repo.fail_run(ctx.deps.pipeline_run_id, "analysis", str(err))
            return _rejection_end(f"Analysis failed: {err}", intent.enhanced_query)

        state.analysis_result = analysis_result
        state.analysis_iterations += 1
        logfire.info("analysis complete", iteration=state.analysis_iterations)

        return ValidateAnalysisNode()


async def _emit_and_finalise(
    state: CoordinatorState,
    intent: IntentAnalysis,
    selection: DatasetSelectionOutput,
    analysis_result: AnalysisResult,
    deps: CoordinatorGraphDeps,
) -> "End[CoordinatorDecision]":
    """Emit the final SSE event, persist the result, and return the terminal End node."""
    _append_sse(state, ToolResultEvent(
        tool="pipeline/analysis",
        result=analysis_result.model_dump(),
    ))
    try:
        await deps.pipeline_repo.save_analysis_result(deps.pipeline_run_id, analysis_result)
    except Exception as err:
        logfire.error("failed to persist analysis result", error=str(err), exc_info=True)
    return End(CoordinatorDecision(
        accepted=True,
        reason="Analysis complete.",
        enhanced_query=intent.enhanced_query,
        dataset_selected=[
            CoordinatorDataset(title=ds.title, path=ds.path)
            for ds in selection.selected_datasets
        ],
        analysis_result=analysis_result,
    ))


@dataclass
class ValidateAnalysisNode(BaseNode[CoordinatorState, CoordinatorGraphDeps, CoordinatorDecision]):
    """Validate analysis quality; route upstream based on root_cause or finalise."""

    MAX_ITERATIONS = 2  # max in-place re-analyze loops (poor_synthesis / chart_quality)

    async def run(
        self, ctx: GraphRunContext[CoordinatorState, CoordinatorGraphDeps]
    ) -> Union[AnalyzeNode, "PlanResearchNode", "SelectDatasetsNode", End[CoordinatorDecision]]:
        state = ctx.state
        intent = _require(state.intent, "intent")
        analysis_result = _require(state.analysis_result, "analysis_result")
        selection = _require(state.dataset_selection, "dataset_selection")

        try:
            validation = await validate_analysis(analysis_result, intent.enhanced_query)
        except Exception as err:
            logfire.warn("analysis validation error (non-fatal), proceeding", error=str(err))
            validation = None

        # ── Happy path ───────────────────────────────────────────────────────────
        if validation is None or validation.valid:
            return await _emit_and_finalise(state, intent, selection, analysis_result, ctx.deps)

        # ── Global pipeline iteration guard ──────────────────────────────────────
        if state.pipeline_iterations >= MAX_PIPELINE_ITERATIONS:
            logfire.warn(
                "pipeline_iterations exhausted, accepting current result",
                pipeline_iterations=state.pipeline_iterations,
                root_cause=validation.root_cause,
                feedback=validation.feedback,
            )
            return await _emit_and_finalise(state, intent, selection, analysis_result, ctx.deps)

        root_cause = validation.root_cause

        # ── wrong_datasets → SelectDatasetsNode ──────────────────────────────────
        if root_cause == "wrong_datasets":
            logfire.info(
                "ValidateAnalysis: routing to SelectDatasetsNode (wrong_datasets)",
                pipeline_iterations=state.pipeline_iterations,
                feedback=validation.feedback,
            )
            state.pipeline_iterations += 1
            state.extraction_feedback = validation.feedback
            state.validation_feedback = None
            state.research_plan = None
            state.extraction_results = []
            state.normalization_result = None
            state.analysis_result = None
            state.analysis_iterations = 0
            state.analysis_feedback = None
            state.selection_iterations = 0
            return SelectDatasetsNode()

        # ── insufficient_data → PlanResearchNode ─────────────────────────────────
        if root_cause == "insufficient_data":
            logfire.info(
                "ValidateAnalysis: routing to PlanResearchNode (insufficient_data)",
                pipeline_iterations=state.pipeline_iterations,
                feedback=validation.feedback,
            )
            state.pipeline_iterations += 1
            state.extraction_feedback = validation.feedback
            state.research_plan = None
            state.extraction_results = []
            state.normalization_result = None
            state.analysis_result = None
            state.analysis_iterations = 0
            state.analysis_feedback = None
            return PlanResearchNode()

        # ── poor_synthesis / chart_quality → AnalyzeNode (in-place retry) ────────
        if state.analysis_iterations < self.MAX_ITERATIONS:
            logfire.info(
                "ValidateAnalysis: routing to AnalyzeNode (in-place retry)",
                root_cause=root_cause,
                iteration=state.analysis_iterations,
                feedback=validation.feedback,
            )
            state.analysis_feedback = validation.feedback
            return AnalyzeNode()

        # ── in-place retries exhausted — accept best result ───────────────────────
        logfire.warn(
            "analysis_iterations exhausted, accepting current result",
            analysis_iterations=state.analysis_iterations,
            root_cause=root_cause,
        )
        return await _emit_and_finalise(state, intent, selection, analysis_result, ctx.deps)


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

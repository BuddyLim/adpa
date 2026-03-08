import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.agents.coordinator_graph import (
    CoordinatorGraphDeps,
    CoordinatorState,
    LoadContextNode,
    coordinator_graph,
    dataset_selector_agent,
    dataset_validator_agent,
    extraction_agent,
    intent_agent,
    research_planner_agent,
)
from app.agents.extraction import PeerSchema
from app.schemas.query import AnalysisResult, AnalysisValidationOutput, ChartConfig

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


# ─── Shared helpers ───────────────────────────────────────────────────────────

def make_mock_repo():
    repo = MagicMock()
    repo.list_datasets = AsyncMock(return_value=json.dumps([
        {"title": "Commute Dataset", "description": "Commute mode data", "path": "commute.csv"}
    ]))
    repo.get_messages = AsyncMock(return_value=[])
    repo.get_conversation_results = AsyncMock(return_value=[])
    repo.add_step = AsyncMock()
    repo.ensure_datasets = AsyncMock(return_value={"Commute Dataset": "uuid-1"})
    repo.save_extraction_results = AsyncMock()
    repo.save_normalization_result = AsyncMock()
    repo.save_analysis_result = AsyncMock()
    repo.fail_run = AsyncMock()
    return repo


def make_state() -> CoordinatorState:
    return CoordinatorState(
        raw_query="How do Singaporeans commute?",
        conversation_id="conv-1",
        pipeline_run_id="run-1",
    )


def make_mock_extraction_deps():
    """Return a mock ExtractionDeps class whose instances act as no-op context managers."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    cls = MagicMock(return_value=instance)
    return cls


# ─── FunctionModel handlers ───────────────────────────────────────────────────

def _intent_feasible(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": True,
        "is_followup": False,
        "domain": "transport",
        "enhanced_query": "Analyse commute modes across Singapore residents.",
        "suggested_prior_datasets": [],
        "rejection_reason": None,
    }))])


def _intent_infeasible(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": False,
        "is_followup": False,
        "domain": "unknown",
        "enhanced_query": "tell me a joke",
        "suggested_prior_datasets": [],
        "rejection_reason": "Query is not related to any policy dataset.",
    }))])


def _selector_selects(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "selected_datasets": [
            {"title": "Commute Dataset", "path": "commute.csv", "selection_reason": "Contains commute mode data."}
        ],
        "cannot_answer": False,
        "reason": "",
    }))])


def _validator_valid(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "valid": True,
        "confirmation_reason": "Dataset covers required commute metrics.",
        "feedback": "",
    }))])


def _planner_happy(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "analysis_type": "comparison",
        "sub_questions": ["Which mode is most used?", "How does usage vary by age?"],
        "key_metrics": ["count", "transport_mode"],
        "extraction_hints": {"Commute Dataset": "Select transport_mode and count."},
        "suggested_chart_types": ["bar", "pie"],
    }))])


def _extraction_happy(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "source_dataset": "Commute Dataset",
        "summary": "Transport mode counts extracted.",
        "rows": [{"transport_mode": "Bus", "count": 1000}],
        "join_keys": ["transport_mode"],
        "sql_query": "SELECT transport_mode, count FROM dataset",
        "truncated": False,
    }))])


def _make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        summary="Bus is the most popular transport mode in Singapore.",
        key_findings=["Bus accounts for 50% of daily trips."],
        chart_configs=[
            ChartConfig(
                chart_type="bar",
                title="Transport Mode Usage",
                description="Daily trips by mode",
                x_key="transport_mode",
                y_keys=["count"],
                series_labels={"count": "Daily Trips"},
                data=[{"transport_mode": "Bus", "count": 1000}],
            )
        ],
    )


# ─── Happy path ───────────────────────────────────────────────────────────────

async def test_happy_path_full_graph():
    """
    Full graph: LoadContext → AnalyzeIntent → SelectDatasets → ValidateDatasetPlan
               → PlanResearch → Extract → Normalize → Analyze → ValidateAnalysis → End.
    Final decision is accepted=True with a populated analysis result.
    """
    repo = make_mock_repo()
    state = make_state()
    deps = CoordinatorGraphDeps(pipeline_repo=repo, pipeline_run_id="run-1")

    fake_schema = PeerSchema(
        title="Commute Dataset",
        columns=[{"name": "transport_mode", "type": "VARCHAR"}, {"name": "count", "type": "BIGINT"}],
        sample_rows=[],
    )
    fake_analysis = _make_analysis_result()

    with (
        intent_agent.override(model=FunctionModel(_intent_feasible)),
        dataset_selector_agent.override(model=FunctionModel(_selector_selects)),
        dataset_validator_agent.override(model=FunctionModel(_validator_valid)),
        research_planner_agent.override(model=FunctionModel(_planner_happy)),
        extraction_agent.override(model=FunctionModel(_extraction_happy)),
        patch("app.agents.coordinator_graph.load_schema", return_value=fake_schema),
        patch("app.agents.coordinator_graph.ExtractionDeps", make_mock_extraction_deps()),
        patch("app.agents.coordinator_graph.run_analysis", new=AsyncMock(return_value=(fake_analysis, None))),
        patch("app.agents.coordinator_graph.validate_analysis", new=AsyncMock(return_value=AnalysisValidationOutput(valid=True))),
    ):
        result = await coordinator_graph.run(LoadContextNode(), state=state, deps=deps)

    decision = result.output

    assert decision.accepted is True
    assert decision.analysis_result is not None
    assert decision.analysis_result.summary != ""
    assert len(decision.analysis_result.chart_configs) >= 1
    assert decision.dataset_selected is not None
    assert len(decision.dataset_selected) == 1
    assert decision.dataset_selected[0].title == "Commute Dataset"

    # Verify DB writes happened in the right order
    repo.save_normalization_result.assert_awaited_once()
    repo.save_analysis_result.assert_awaited_once()
    repo.fail_run.assert_not_awaited()

    # No retry loops triggered
    assert state.pipeline_iterations == 0


# ─── Infeasible query → early termination ─────────────────────────────────────

async def test_infeasible_query_short_circuits():
    """
    Intent agent rejects the query. Graph terminates after AnalyzeIntentNode.
    No dataset selection, extraction, analysis, or DB writes occur.
    """
    repo = make_mock_repo()
    state = make_state()
    deps = CoordinatorGraphDeps(pipeline_repo=repo, pipeline_run_id="run-1")

    with intent_agent.override(model=FunctionModel(_intent_infeasible)):
        result = await coordinator_graph.run(LoadContextNode(), state=state, deps=deps)

    decision = result.output

    assert decision.accepted is False
    assert decision.reason == "Query is not related to any policy dataset."
    assert decision.analysis_result is None
    assert decision.dataset_selected is None

    # Nothing past AnalyzeIntentNode should have been touched
    repo.ensure_datasets.assert_not_awaited()
    repo.save_extraction_results.assert_not_awaited()
    repo.save_normalization_result.assert_not_awaited()
    repo.save_analysis_result.assert_not_awaited()
    repo.fail_run.assert_not_awaited()

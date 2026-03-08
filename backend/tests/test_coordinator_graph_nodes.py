import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_graph import End

import app.agents.coordinator_nodes as coordinator_nodes
from app.agents.coordinator import dataset_validator_agent, intent_agent
from app.agents.coordinator_nodes import (
    AnalyzeIntentNode,
    AnalyzeNode,
    LoadContextNode,
    NormalizeNode,
    PlanResearchNode,
    SelectDatasetsNode,
    ValidateAnalysisNode,
    ValidateDatasetPlanNode,
)
from app.agents.coordinator_state import CoordinatorState
from app.schemas.query import (
    AnalysisResult,
    AnalysisValidationOutput,
    ChartConfig,
    DatasetInfo,
    DatasetSelectionOutput,
    ExtractionResult,
    IntentAnalysis,
    NormalizationResult,
    SelectedDataset,
)

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def make_mock_repo():
    repo = MagicMock()
    repo.list_datasets = AsyncMock(return_value=json.dumps([
        {"title": "Commute Dataset", "description": "Commute mode data", "path": "commute.csv"}
    ]))
    repo.get_messages = AsyncMock(return_value=[])
    repo.get_conversation_results = AsyncMock(return_value=[])
    repo.add_step = AsyncMock()
    repo.ensure_datasets = AsyncMock(return_value={"Commute Dataset": "uuid-1"})
    repo.save_normalization_result = AsyncMock()
    repo.save_analysis_result = AsyncMock()
    repo.fail_run = AsyncMock()
    return repo


def make_ctx(state: CoordinatorState, repo=None):
    ctx = MagicMock()
    ctx.state = state
    ctx.deps = MagicMock()
    ctx.deps.pipeline_repo = repo or make_mock_repo()
    ctx.deps.pipeline_run_id = "run-123"
    return ctx


def make_state(**kwargs) -> CoordinatorState:
    return CoordinatorState(
        raw_query="How do Singaporeans commute?",
        conversation_id="conv-1",
        pipeline_run_id="run-1",
        **kwargs,
    )


def make_intent() -> IntentAnalysis:
    return IntentAnalysis(
        is_feasible=True,
        is_followup=False,
        domain="transport",
        enhanced_query="Analyse commute modes across Singapore residents.",
        suggested_prior_datasets=[],
    )


def make_selection() -> DatasetSelectionOutput:
    return DatasetSelectionOutput(
        selected_datasets=[
            SelectedDataset(
                title="Commute Dataset",
                path="commute.csv",
                selection_reason="Contains commute mode data.",
            )
        ],
        cannot_answer=False,
    )


def make_extraction_result(source: str = "commute.csv") -> ExtractionResult:
    return ExtractionResult(
        source_dataset=source,
        summary="Transport mode counts.",
        rows=[{"transport_mode": "Bus", "count": 1000, "source": source}],
        join_keys=["transport_mode"],
        sql_query="SELECT * FROM dataset",
        truncated=False,
    )


def make_analysis_result() -> AnalysisResult:
    return AnalysisResult(
        summary="Bus is the most common transport mode in Singapore.",
        key_findings=[
            "Bus accounts for 50% of daily trips (5,000 users).",
            "MRT serves 30% of commuters with 3,000 daily trips.",
            "Car usage is at 20% with approximately 2,000 daily users.",
        ],
        chart_configs=[
            ChartConfig(
                chart_type="bar",
                title="Transport Mode Usage",
                description="Daily trips by transport mode",
                x_key="transport_mode",
                y_keys=["count"],
                series_labels={"count": "Daily Trips"},
                data=[{"transport_mode": "Bus", "count": 5000}],
            ),
            ChartConfig(
                chart_type="pie",
                title="Mode Share",
                description="Proportion of each mode",
                name_key="transport_mode",
                value_key="count",
                data=[{"transport_mode": "Bus", "count": 5000}],
            ),
        ],
    )


# ─── LoadContextNode ──────────────────────────────────────────────────────────

async def test_load_context_node_happy():
    state = make_state()
    repo = make_mock_repo()
    ctx = make_ctx(state, repo)

    result = await LoadContextNode().run(ctx)

    assert isinstance(result, AnalyzeIntentNode)
    assert len(state.available_datasets) == 1
    assert state.available_datasets[0].title == "Commute Dataset"
    repo.get_messages.assert_awaited_once_with("conv-1")


async def test_load_context_node_bad():
    state = make_state()
    repo = make_mock_repo()
    repo.list_datasets = AsyncMock(side_effect=RuntimeError("DB connection failed"))
    ctx = make_ctx(state, repo)

    with pytest.raises(RuntimeError, match="DB connection failed"):
        await LoadContextNode().run(ctx)


# ─── AnalyzeIntentNode ────────────────────────────────────────────────────────

def _intent_feasible_handler(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": True,
        "is_followup": False,
        "domain": "transport",
        "enhanced_query": "Analyse commute modes across Singapore residents.",
        "suggested_prior_datasets": [],
        "rejection_reason": None,
    }))])


def _intent_infeasible_handler(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": False,
        "is_followup": False,
        "domain": "unknown",
        "enhanced_query": "tell me about everything",
        "suggested_prior_datasets": [],
        "rejection_reason": "Query is too vague.",
    }))])


async def test_analyze_intent_node_feasible():
    state = make_state()
    ctx = make_ctx(state)

    with intent_agent.override(model=FunctionModel(_intent_feasible_handler)):
        result = await AnalyzeIntentNode().run(ctx)

    assert isinstance(result, SelectDatasetsNode)
    assert state.intent is not None
    assert state.intent.is_feasible is True


async def test_analyze_intent_node_infeasible():
    state = make_state()
    ctx = make_ctx(state)

    with intent_agent.override(model=FunctionModel(_intent_infeasible_handler)):
        result = await AnalyzeIntentNode().run(ctx)

    assert isinstance(result, End)
    assert result.data.accepted is False
    assert result.data.reason != ""


# ─── ValidateDatasetPlanNode ──────────────────────────────────────────────────

def _validator_valid_handler(_m, _i):
    return ModelResponse(parts=[TextPart(json.dumps({
        "valid": True,
        "confirmation_reason": "Datasets cover the required metrics.",
        "feedback": "",
    }))])


async def test_validate_dataset_plan_node_cannot_answer():
    """When selector says cannot_answer, node short-circuits to End with no LLM call."""
    state = make_state()
    state.intent = make_intent()
    state.dataset_selection = DatasetSelectionOutput(
        selected_datasets=[],
        cannot_answer=True,
        reason="No relevant dataset found.",
    )
    ctx = make_ctx(state)

    result = await ValidateDatasetPlanNode().run(ctx)

    assert isinstance(result, End)
    assert result.data.accepted is False


async def test_validate_dataset_plan_node_valid():
    """When validator approves, node proceeds to PlanResearchNode."""
    state = make_state()
    state.intent = make_intent()
    state.dataset_selection = make_selection()
    state.available_datasets = [
        DatasetInfo(title="Commute Dataset", description="Commute mode data", path="commute.csv")
    ]
    ctx = make_ctx(state)

    with dataset_validator_agent.override(model=FunctionModel(_validator_valid_handler)):
        result = await ValidateDatasetPlanNode().run(ctx)

    assert isinstance(result, PlanResearchNode)


# ─── NormalizeNode ────────────────────────────────────────────────────────────

async def test_normalize_node_single_dataset():
    """Single extraction result skips the normalization LLM and wraps result directly."""
    state = make_state()
    state.intent = make_intent()
    state.extraction_results = [make_extraction_result()]
    ctx = make_ctx(state)

    result = await NormalizeNode().run(ctx)

    assert isinstance(result, AnalyzeNode)
    assert state.normalization_result is not None
    assert state.normalization_result.notes == "Single dataset - normalization skipped."
    assert len(state.normalization_result.unified_rows) == 1


async def test_normalize_node_normalization_raises():
    """When run_normalization raises for multi-dataset input, node returns End rejection."""
    state = make_state()
    state.intent = make_intent()
    state.extraction_results = [
        make_extraction_result("census.csv"),
        make_extraction_result("survey.csv"),
    ]
    repo = make_mock_repo()
    ctx = make_ctx(state, repo)

    with patch.object(coordinator_nodes, "run_normalization", side_effect=RuntimeError("norm failed")):
        result = await NormalizeNode().run(ctx)

    assert isinstance(result, End)
    assert result.data.accepted is False
    repo.fail_run.assert_awaited_once()


# ─── ValidateAnalysisNode ─────────────────────────────────────────────────────

async def test_validate_analysis_node_valid():
    """Valid analysis result finalises the pipeline as accepted."""
    state = make_state()
    state.intent = make_intent()
    state.dataset_selection = make_selection()
    state.analysis_result = make_analysis_result()
    ctx = make_ctx(state)

    valid_output = AnalysisValidationOutput(valid=True)
    with patch.object(coordinator_nodes, "validate_analysis", return_value=valid_output):
        result = await ValidateAnalysisNode().run(ctx)

    assert isinstance(result, End)
    assert result.data.accepted is True


async def test_validate_analysis_node_wrong_datasets():
    """wrong_datasets root cause routes back to SelectDatasetsNode and increments pipeline_iterations."""
    state = make_state()
    state.intent = make_intent()
    state.dataset_selection = make_selection()
    state.analysis_result = make_analysis_result()
    state.pipeline_iterations = 0
    ctx = make_ctx(state)

    bad_output = AnalysisValidationOutput(
        valid=False,
        feedback="Datasets contain housing data, not transport metrics.",
        root_cause="wrong_datasets",
    )
    with patch.object(coordinator_nodes, "validate_analysis", return_value=bad_output):
        result = await ValidateAnalysisNode().run(ctx)

    assert isinstance(result, SelectDatasetsNode)
    assert state.pipeline_iterations == 1
    assert state.extraction_feedback is not None

import json

import pytest
from pydantic_ai import ModelRetry, models
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from unittest.mock import MagicMock

from app.agents.normalization import (
    NormalizationDeps,
    compare_column_domains,
    normalization_agent,
    validate_unified_rows,
)
from app.schemas.query import ExtractionResult, NormalizationResult

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def two_extraction_results():
    return [
        ExtractionResult(
            source_dataset="census_2020.csv",
            summary="Transport mode counts from 2020 census",
            rows=[
                {"transport_mode": "Bus", "count": 5000, "source": "census_2020"},
                {"transport_mode": "MRT", "count": 8000, "source": "census_2020"},
            ],
            join_keys=["transport_mode"],
            sql_query="SELECT transport_mode, count FROM dataset",
            truncated=False,
        ),
        ExtractionResult(
            source_dataset="survey_2023.csv",
            summary="Transport mode counts from 2023 survey",
            rows=[
                {"transport_mode": "Bus", "count": 4500, "source": "survey_2023"},
                {"transport_mode": "Train", "count": 9000, "source": "survey_2023"},
            ],
            join_keys=["transport_mode"],
            sql_query="SELECT transport_mode, count FROM dataset",
            truncated=False,
        ),
    ]


def make_ctx(extraction_results):
    ctx = MagicMock()
    ctx.deps = NormalizationDeps(extraction_results=extraction_results)
    return ctx


# --- validate_unified_rows ---

def test_validate_unified_rows_valid(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [
        {"transport_mode": "Bus",   "count": 5000, "source": "census_2020"},
        {"transport_mode": "MRT",   "count": 8000, "source": "census_2020"},
        {"transport_mode": "Bus",   "count": 4500, "source": "survey_2023"},
        {"transport_mode": "Train", "count": 9000, "source": "survey_2023"},
    ]
    result = validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count", "source"])
    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_unified_rows_empty_raises(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    with pytest.raises(ModelRetry, match="empty"):
        validate_unified_rows(ctx, rows=[], columns=["transport_mode", "count", "source"])


def test_validate_unified_rows_missing_source_column(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [{"transport_mode": "Bus", "count": 5000}]
    with pytest.raises(ModelRetry, match="source tracking"):
        validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count"])


def test_validate_unified_rows_missing_column_in_row(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [{"transport_mode": "Bus", "source": "census_2020"}]  # missing "count"
    with pytest.raises(ModelRetry, match="missing columns"):
        validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count", "source"])


def test_validate_unified_rows_null_value(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [{"transport_mode": "Bus", "count": None, "source": "census_2020"}]
    with pytest.raises(ModelRetry, match="null"):
        validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count", "source"])


def test_validate_unified_rows_negative_count(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [{"transport_mode": "Bus", "count": -100, "source": "census_2020"}]
    with pytest.raises(ModelRetry, match="negative"):
        validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count", "source"])


def test_validate_unified_rows_1000x_magnitude_jump(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    rows = [
        {"transport_mode": "Bus", "count": 5,    "source": "census_2020"},  # in thousands
        {"transport_mode": "MRT", "count": 8,    "source": "census_2020"},
        {"transport_mode": "Bus", "count": 4500, "source": "survey_2023"},  # raw
        {"transport_mode": "MRT", "count": 9000, "source": "survey_2023"},
    ]
    with pytest.raises(ModelRetry, match="1000x"):
        validate_unified_rows(ctx, rows=rows, columns=["transport_mode", "count", "source"])


# --- compare_column_domains ---

def test_compare_column_domains_overlap(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    result = compare_column_domains(
        ctx,
        col_a_values=["Bus", "MRT"],
        col_b_values=["Bus", "Train"],
        col_a_label="census_2020",
        col_b_label="survey_2023",
    )
    assert "Bus" in result["overlap"]
    assert "MRT" in result["only_in_census_2020"]
    assert "Train" in result["only_in_survey_2023"]
    assert result["overlap_count"] == 1


def test_compare_column_domains_case_insensitive(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    result = compare_column_domains(
        ctx,
        col_a_values=["Bus", "MRT"],
        col_b_values=["bus", "mrt"],
    )
    assert result["overlap_count"] == 2
    assert result["only_in_source_a"] == []
    assert result["only_in_source_b"] == []


def test_compare_column_domains_no_overlap(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    result = compare_column_domains(
        ctx,
        col_a_values=["A", "B"],
        col_b_values=["C", "D"],
    )
    assert result["overlap_count"] == 0
    assert result["jaccard_similarity"] == 0.0


def test_compare_column_domains_full_overlap(two_extraction_results):
    ctx = make_ctx(two_extraction_results)
    result = compare_column_domains(
        ctx,
        col_a_values=["Bus", "MRT"],
        col_b_values=["Bus", "MRT"],
    )
    assert result["overlap_count"] == 2
    assert result["jaccard_similarity"] == 1.0


# --- Integration test ---

def passing_normalization_handler():
    """
    Simulates a 3-turn normalization loop:
      1. call compare_column_domains
      2. call validate_unified_rows (returns valid=true)
      3. return final NormalizationResult
    """
    call_count = 0

    def handler(messages, info):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return ModelResponse(parts=[
                ToolCallPart(
                    tool_name="compare_column_domains",
                    args=json.dumps({
                        "col_a_values": ["Bus", "MRT"],
                        "col_b_values": ["Bus", "Train"],
                        "col_a_label": "census_2020",
                        "col_b_label": "survey_2023",
                    }),
                    tool_call_id="call_1",
                )
            ])
        elif call_count == 2:
            return ModelResponse(parts=[
                ToolCallPart(
                    tool_name="validate_unified_rows",
                    args=json.dumps({
                        "rows": [
                            {"transport_mode": "Bus",   "count": 5000, "source": "census_2020"},
                            {"transport_mode": "MRT",   "count": 8000, "source": "census_2020"},
                            {"transport_mode": "Bus",   "count": 4500, "source": "survey_2023"},
                            {"transport_mode": "Train", "count": 9000, "source": "survey_2023"},
                        ],
                        "columns": ["transport_mode", "count", "source"],
                    }),
                    tool_call_id="call_2",
                )
            ])
        else:
            return ModelResponse(parts=[
                TextPart(json.dumps({
                    "notes": "MRT (census) kept as-is; Train (survey) kept as-is. Bus overlaps both sources.",
                    "unified_rows": [
                        {"transport_mode": "Bus",   "count": 5000, "source": "census_2020"},
                        {"transport_mode": "MRT",   "count": 8000, "source": "census_2020"},
                        {"transport_mode": "Bus",   "count": 4500, "source": "survey_2023"},
                        {"transport_mode": "Train", "count": 9000, "source": "survey_2023"},
                    ],
                    "columns": ["transport_mode", "count", "source"],
                }))
            ])

    return handler


async def test_normalization_happy_flow(two_extraction_results):
    with normalization_agent.override(model=FunctionModel(passing_normalization_handler())):
        result = await normalization_agent.run(
            "Normalize transport mode data",
            deps=NormalizationDeps(extraction_results=two_extraction_results),
        )

    output: NormalizationResult = result.output
    assert len(output.unified_rows) == 4
    assert "transport_mode" in output.columns
    assert "source" in output.columns
    assert output.notes != ""

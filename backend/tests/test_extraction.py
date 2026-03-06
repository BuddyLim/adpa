import csv
import json

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.agents.extraction import ExtractionDeps, extraction_agent
from app.schemas.query import ExtractionResult

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "commute.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["transport_mode", "count"])
        writer.writerow(["Bus", "1000"])
        writer.writerow(["MRT", "2000"])
        writer.writerow(["Car", "3000"])
    return str(path)


def passing_happy_handler():
    """
    Simulates a 3-turn agent loop:
      1. call load_dataset
      2. call execute_query with valid SQL
      3. return final ExtractionResult
    """
    call_count = 0

    def handler(messages, info):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return ModelResponse(parts=[
                ToolCallPart(tool_name="load_dataset", args="{}", tool_call_id="call_1")
            ])
        elif call_count == 2:
            return ModelResponse(parts=[
                ToolCallPart(
                    tool_name="execute_query",
                    args=json.dumps({"sql": "SELECT transport_mode, count FROM dataset"}),
                    tool_call_id="call_2",
                )
            ])
        else:
            return ModelResponse(parts=[
                TextPart(json.dumps({
                    "source_dataset": "commute.csv",
                    "summary": "Extracted transport mode counts for all modes.",
                    "rows": [
                        {"transport_mode": "Bus", "count": 1000},
                        {"transport_mode": "MRT", "count": 2000},
                        {"transport_mode": "Car", "count": 3000},
                    ],
                    "join_keys": [],
                    "sql_query": "SELECT transport_mode, count FROM dataset",
                }))
            ])

    return handler


def failing_sql_handler(messages, info):
    """Always calls execute_query with SQL referencing a non-existent table, exhausting retries."""
    return ModelResponse(parts=[
        ToolCallPart(
            tool_name="execute_query",
            args=json.dumps({"sql": "SELECT * FROM nonexistent_table"}),
            tool_call_id="call_1",
        )
    ])


async def test_extraction_happy_flow(csv_file):
    with extraction_agent.override(model=FunctionModel(passing_happy_handler())):
        with ExtractionDeps(dataset_path=csv_file, dataset_title="commute.csv") as deps:
            result = await extraction_agent.run(
                "Extract all transport modes and their counts",
                deps=deps,
            )

    output: ExtractionResult = result.output
    assert output.source_dataset == "commute.csv"
    assert output.summary != ""
    assert len(output.rows) == 3
    assert output.sql_query != ""
    assert all("transport_mode" in row for row in output.rows)


async def test_extraction_failing_sql_exhausts_retries():
    with pytest.raises(Exception):
        with extraction_agent.override(model=FunctionModel(failing_sql_handler)):
            await extraction_agent.run(
                "Extract all transport modes",
                deps=ExtractionDeps(
                    dataset_path="/nonexistent/path.csv",
                    dataset_title="missing.csv",
                ),
            )


# --- Unit tests for new tools ---

@pytest.fixture
def extraction_ctx(csv_file):
    from unittest.mock import MagicMock
    ctx = MagicMock()
    deps = ExtractionDeps(dataset_path=csv_file, dataset_title="commute.csv")
    deps.__enter__()
    ctx.deps = deps
    ctx.retry = 0
    yield ctx
    deps.__exit__(None, None, None)


@pytest.fixture
def large_extraction_ctx(large_csv_file):
    from unittest.mock import MagicMock
    ctx = MagicMock()
    deps = ExtractionDeps(dataset_path=large_csv_file, dataset_title="commute.csv")
    deps.__enter__()
    ctx.deps = deps
    ctx.retry = 0
    yield ctx
    deps.__exit__(None, None, None)


def test_get_unique_values(extraction_ctx):
    from app.agents.extraction import get_unique_values
    result = get_unique_values(extraction_ctx, column="transport_mode")
    assert result["column"] == "transport_mode"
    assert set(result["distinct_values"]) == {"Bus", "MRT", "Car"}
    assert result["count"] == 3


def test_get_unique_values_bad_column(extraction_ctx):
    from pydantic_ai import ModelRetry
    from app.agents.extraction import get_unique_values
    with pytest.raises(ModelRetry):
        get_unique_values(extraction_ctx, column="nonexistent_column")


def test_count_rows(extraction_ctx):
    from app.agents.extraction import count_rows
    result = count_rows(extraction_ctx, sql="SELECT * FROM dataset")
    assert result["count"] == 3
    assert "sql_used" in result


def test_count_rows_with_filter(extraction_ctx):
    from app.agents.extraction import count_rows
    result = count_rows(extraction_ctx, sql="SELECT * FROM dataset WHERE transport_mode = 'Bus'")
    assert result["count"] == 1


@pytest.fixture
def large_csv_file(tmp_path):
    path = tmp_path / "large.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "value"])
        for i in range(600):
            writer.writerow([i, i * 10])
    return str(path)


def test_execute_query_truncation(large_extraction_ctx):
    from app.agents.extraction import execute_query, EXECUTE_QUERY_ROW_LIMIT
    result = execute_query(large_extraction_ctx, sql="SELECT * FROM dataset")
    assert result["row_count"] == EXECUTE_QUERY_ROW_LIMIT
    assert result["truncated"] is True


def test_execute_query_no_truncation(extraction_ctx):
    from app.agents.extraction import execute_query
    result = execute_query(extraction_ctx, sql="SELECT * FROM dataset")
    assert result["row_count"] == 3
    assert result["truncated"] is False

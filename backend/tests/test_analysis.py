import pytest
from unittest.mock import MagicMock

from pydantic_ai import ModelRetry, models

from app.agents.analysis import (
    AnalysisDeps,
    compute_statistics,
    compute_trend,
    group_and_aggregate,
    rank_values,
)

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def analysis_ctx():
    ctx = MagicMock()
    ctx.deps = AnalysisDeps(
        unified_rows=[
            {"transport_mode": "Bus", "count": 1000},
            {"transport_mode": "MRT", "count": 2000},
            {"transport_mode": "Car", "count": 3000},
        ],
        columns=["transport_mode", "count"],
        query="What are the most popular transport modes?",
    )
    return ctx


@pytest.fixture
def trend_ctx():
    ctx = MagicMock()
    ctx.deps = AnalysisDeps(
        unified_rows=[
            {"year": 2020, "count": 100},
            {"year": 2021, "count": 200},
            {"year": 2022, "count": 300},
        ],
        columns=["year", "count"],
        query="How has transport usage changed over time?",
    )
    return ctx


# ─── compute_statistics ───────────────────────────────────────────────────────

def test_compute_statistics_happy(analysis_ctx):
    result = compute_statistics(analysis_ctx, column="count")
    assert result["column"] == "count"
    assert result["count"] == 3
    assert result["min"] == 1000
    assert result["max"] == 3000
    assert result["mean"] == 2000.0


def test_compute_statistics_nonexistent_column(analysis_ctx):
    with pytest.raises(ModelRetry):
        compute_statistics(analysis_ctx, column="nonexistent_column")


# ─── rank_values ──────────────────────────────────────────────────────────────

def test_rank_values_happy(analysis_ctx):
    result = rank_values(analysis_ctx, sort_column="count", top_n=2)
    assert result["sort_column"] == "count"
    assert len(result["rows"]) == 2
    # Default ascending=False → highest first
    assert result["rows"][0]["count"] == 3000


def test_rank_values_nonexistent_column(analysis_ctx):
    with pytest.raises(ModelRetry):
        rank_values(analysis_ctx, sort_column="nonexistent")


# ─── compute_trend ────────────────────────────────────────────────────────────

def test_compute_trend_happy(trend_ctx):
    result = compute_trend(trend_ctx, x_column="year", y_column="count")
    assert result["direction"] == "up"
    assert result["slope"] > 0
    assert result["n_points"] == 3


def test_compute_trend_insufficient_data():
    ctx = MagicMock()
    ctx.deps = AnalysisDeps(
        unified_rows=[{"year": 2020, "count": 100}],
        columns=["year", "count"],
        query="trend?",
    )
    with pytest.raises(ModelRetry, match="at least 2"):
        compute_trend(ctx, x_column="year", y_column="count")


# ─── group_and_aggregate ──────────────────────────────────────────────────────

def test_group_and_aggregate_happy(analysis_ctx):
    result = group_and_aggregate(
        analysis_ctx,
        group_by_column="transport_mode",
        agg_column="count",
        agg_fn="sum",
    )
    assert result["agg_fn"] == "sum"
    groups = {r["group"]: r["value"] for r in result["result"]}
    assert groups["Bus"] == 1000
    assert groups["MRT"] == 2000
    assert groups["Car"] == 3000


def test_group_and_aggregate_nonexistent_column(analysis_ctx):
    with pytest.raises(ModelRetry):
        group_and_aggregate(
            analysis_ctx,
            group_by_column="nonexistent",
            agg_column="count",
            agg_fn="sum",
        )

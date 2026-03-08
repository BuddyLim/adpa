"""
Eval 2 — Analysis Agent Quality

Tests whether analysis_agent produces structured, quantitative, chart-ready output
given pre-baked normalized data.

Run as a pytest test (makes real LLM calls):
    cd backend && pytest evals/eval_analysis_agent.py -v -s

Run as a standalone script to see the full report table:
    cd backend && python -m evals.eval_analysis_agent
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.agents.analysis import run_analysis
from app.schemas.query import AnalysisResult, NormalizationResult


# ─── Task input / function ────────────────────────────────────────────────────

@dataclass
class AnalysisInput:
    rows: list[dict]
    columns: list[str]
    query: str


async def run_analysis_task(inp: AnalysisInput) -> AnalysisResult:
    norm = NormalizationResult(
        notes="",
        unified_rows=inp.rows,
        columns=inp.columns,
    )
    result, _ = await run_analysis(norm, inp.query)
    return result


# ─── Evaluators ───────────────────────────────────────────────────────────────

class HasQuantitativeFindings(Evaluator[AnalysisInput, AnalysisResult]):
    """
    Scores the fraction of key_findings that contain at least one digit (number).
    Returns 1.0 if all findings are quantitative, else the fraction that are.
    """

    def evaluate(self, ctx: EvaluatorContext[AnalysisInput, AnalysisResult]) -> float:
        findings = ctx.output.key_findings
        if not findings:
            return 0.0
        quantitative = sum(1 for f in findings if re.search(r"\d", f))
        return quantitative / len(findings)


class ChartCountInRange(Evaluator[AnalysisInput, AnalysisResult]):
    """1.0 if there are 2–3 chart_configs, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext[AnalysisInput, AnalysisResult]) -> float:
        n = len(ctx.output.chart_configs)
        return 1.0 if 2 <= n <= 3 else 0.0


class SummaryNotEmpty(Evaluator[AnalysisInput, AnalysisResult]):
    """1.0 if the summary contains at least 20 words, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext[AnalysisInput, AnalysisResult]) -> float:
        word_count = len(ctx.output.summary.split())
        return 1.0 if word_count >= 20 else 0.0


# ─── Pre-baked test data ──────────────────────────────────────────────────────

_TRANSPORT_ROWS = [
    {"transport_mode": "MRT", "daily_trips": 3_200_000},
    {"transport_mode": "Bus", "daily_trips": 3_800_000},
    {"transport_mode": "LRT", "daily_trips": 420_000},
    {"transport_mode": "Taxi", "daily_trips": 950_000},
    {"transport_mode": "Private Car", "daily_trips": 7_500_000},
]

_EMPLOYMENT_ROWS = [
    {"year": 2015, "employment_rate": 67.0},
    {"year": 2016, "employment_rate": 66.8},
    {"year": 2017, "employment_rate": 67.5},
    {"year": 2018, "employment_rate": 68.2},
    {"year": 2019, "employment_rate": 68.6},
    {"year": 2020, "employment_rate": 66.1},
    {"year": 2021, "employment_rate": 67.0},
    {"year": 2022, "employment_rate": 68.9},
    {"year": 2023, "employment_rate": 69.3},
]

# ─── Dataset ──────────────────────────────────────────────────────────────────

dataset: Dataset[AnalysisInput, AnalysisResult] = Dataset(
    cases=[
        Case(
            name="transport_mode_comparison",
            inputs=AnalysisInput(
                rows=_TRANSPORT_ROWS,
                columns=["transport_mode", "daily_trips"],
                query="Compare daily trips by transport mode",
            ),
        ),
        Case(
            name="employment_rate_trend",
            inputs=AnalysisInput(
                rows=_EMPLOYMENT_ROWS,
                columns=["year", "employment_rate"],
                query="How has the resident employment rate trended since 2015?",
            ),
        ),
    ],
    evaluators=[
        HasQuantitativeFindings(),
        ChartCountInRange(),
        SummaryNotEmpty(),
    ],
)


# ─── Pytest entry point ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analysis_agent_evals() -> None:
    """Run analysis agent evals and assert quality thresholds."""
    report = await dataset.evaluate(run_analysis_task)
    report.print(include_input=True, include_output=True)

    agg = report.averages()
    scores = agg.scores if agg is not None else {}

    quant_score = scores.get("HasQuantitativeFindings", 0.0)
    chart_score = scores.get("ChartCountInRange", 0.0)
    summary_score = scores.get("SummaryNotEmpty", 0.0)

    assert quant_score >= 0.80, (
        f"HasQuantitativeFindings score {quant_score:.2f} is below threshold 0.80"
    )
    assert chart_score >= 0.80, (
        f"ChartCountInRange score {chart_score:.2f} is below threshold 0.80"
    )
    assert summary_score >= 0.80, (
        f"SummaryNotEmpty score {summary_score:.2f} is below threshold 0.80"
    )


# ─── Standalone script ────────────────────────────────────────────────────────

if __name__ == "__main__":
    report = dataset.evaluate_sync(run_analysis_task)
    report.print(include_input=True, include_output=True)

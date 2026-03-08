"""
Eval 1 — Intent Agent Classification

Tests whether intent_agent correctly gates queries (feasible vs. infeasible)
and identifies policy domains.

Run as a pytest test (makes real LLM calls):
    cd backend && pytest evals/eval_intent_agent.py -v -s

Run as a standalone script to see the full report table:
    cd backend && python -m evals.eval_intent_agent
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.agents.coordinator_graph import intent_agent
from app.schemas.query import IntentAnalysis


# ─── Task function ────────────────────────────────────────────────────────────

async def run_intent(query: str) -> IntentAnalysis:
    result = await intent_agent.run(query)
    return result.output


# ─── Expected output schema ───────────────────────────────────────────────────

class IntentExpected:
    def __init__(self, is_feasible: bool, domain: str | None = None):
        self.is_feasible = is_feasible
        self.domain = domain


# ─── Evaluators ───────────────────────────────────────────────────────────────

class FeasibilityCorrect(Evaluator[str, IntentAnalysis]):
    """1.0 if output.is_feasible matches expected, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext[str, IntentAnalysis]) -> float:
        if ctx.expected_output is None:
            return 1.0
        expected: IntentExpected = ctx.expected_output  # type: ignore[assignment]
        return 1.0 if ctx.output.is_feasible == expected.is_feasible else 0.0


class DomainCorrect(Evaluator[str, IntentAnalysis]):
    """
    1.0 if domain matches expected_domain (case-insensitive substring).
    Skipped (returns 1.0) when the query is infeasible or no expected domain.
    """

    def evaluate(self, ctx: EvaluatorContext[str, IntentAnalysis]) -> float:
        if ctx.expected_output is None:
            return 1.0
        expected: IntentExpected = ctx.expected_output  # type: ignore[assignment]
        # Skip domain check for infeasible queries
        if not expected.is_feasible or expected.domain is None:
            return 1.0
        expected_domain = expected.domain.lower()
        actual_domain = (ctx.output.domain or "").lower()
        return 1.0 if expected_domain in actual_domain or actual_domain in expected_domain else 0.0


class RejectionReasonPresent(Evaluator[str, IntentAnalysis]):
    """
    For infeasible queries: 1.0 if rejection_reason is non-empty, else 0.0.
    For feasible queries: always 1.0 (not applicable).
    """

    def evaluate(self, ctx: EvaluatorContext[str, IntentAnalysis]) -> float:
        if ctx.expected_output is None:
            return 1.0
        expected: IntentExpected = ctx.expected_output  # type: ignore[assignment]
        if not expected.is_feasible:
            has_reason = bool(ctx.output.rejection_reason and ctx.output.rejection_reason.strip())
            return 1.0 if has_reason else 0.0
        return 1.0


# ─── Dataset ──────────────────────────────────────────────────────────────────

dataset: Dataset[str, IntentAnalysis] = Dataset(
    cases=[
        Case(
            name="mrt_commute_pct",
            inputs="What percentage of Singaporeans commute by MRT?",
            expected_output=IntentExpected(is_feasible=True, domain="transport"),
        ),
        Case(
            name="employment_rate_trend",
            inputs="How has the resident employment rate changed from 2015 to 2023?",
            expected_output=IntentExpected(is_feasible=True, domain="employment"),
        ),
        Case(
            name="housing_prices_comparison",
            inputs="Compare housing prices across planning areas in 2022",
            expected_output=IntentExpected(is_feasible=True, domain="housing"),
        ),
        Case(
            name="joke_rejected",
            inputs="Tell me a joke",
            expected_output=IntentExpected(is_feasible=False),
        ),
        Case(
            name="weather_rejected",
            inputs="What is the current weather in Singapore?",
            expected_output=IntentExpected(is_feasible=False),
        ),
        Case(
            name="vague_singapore_rejected",
            inputs="Tell me about Singapore",
            expected_output=IntentExpected(is_feasible=False),
        ),
    ],
    evaluators=[
        FeasibilityCorrect(),
        DomainCorrect(),
        RejectionReasonPresent(),
    ],
)


# ─── Pytest entry point ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intent_agent_evals() -> None:
    """Run intent agent evals and assert quality thresholds."""
    report = await dataset.evaluate(run_intent)
    report.print(include_input=True, include_output=True)

    agg = report.averages()
    scores = agg.scores if agg is not None else {}

    feasibility_score = scores.get("FeasibilityCorrect", 0.0)
    domain_score = scores.get("DomainCorrect", 0.0)

    assert feasibility_score >= 0.85, (
        f"FeasibilityCorrect score {feasibility_score:.2f} is below threshold 0.85"
    )
    assert domain_score >= 0.80, (
        f"DomainCorrect score {domain_score:.2f} is below threshold 0.80"
    )


# ─── Standalone script ────────────────────────────────────────────────────────

if __name__ == "__main__":
    report = dataset.evaluate_sync(run_intent)
    report.print(include_input=True, include_output=True)

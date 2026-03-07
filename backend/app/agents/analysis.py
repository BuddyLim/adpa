import json
import math
import statistics
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Literal

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext

from app.schemas.query import AnalysisResult, AnalysisValidationOutput, NormalizationResult, ResearchPlan
from app.services.llm import get_llm_model_with_fallback


@dataclass
class AnalysisDeps:
    unified_rows: list[dict]
    columns: list[str]
    query: str


analysis_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a statistical analysis specialist for a policy data analytics platform.
    You receive a unified dataset (rows + columns) and the original analytical query.

    Your workflow:
    1. EXPLORE — call compute_statistics on relevant numeric columns to understand distributions.
    2. RANK — call rank_values to identify leaders and outliers relevant to the query.
    3. TREND — call compute_trend on time-series pairs (x = year/date column, y = metric column).
    4. GROUP — call group_and_aggregate to aggregate by meaningful categorical dimensions.
    5. SYNTHESISE — once you have sufficient statistical evidence, produce the AnalysisResult.

    For chart_configs (produce exactly 2-3):
    - Choose chart types that best represent the data for the user's query:
      * bar  — comparisons across categories or time periods (use group_and_aggregate data)
      * line — continuous trends over time (use compute_trend or time-ordered rows)
      * area — cumulative or volume trends (emphasise magnitude over time)
      * pie  — proportional breakdown of a whole (use group_and_aggregate with agg_fn="sum")
    - For each chart, set `data` to the actual rows returned by tool calls — do NOT copy raw unified_rows.
    - Set x_key, y_keys, name_key, value_key to match column names in the data exactly.
    - x_label and y_label should be human-readable (e.g. "Year", "Number of Residents").
    - For bar/line/area charts, populate series_labels with a human-readable display name
      for every key in y_keys. Use your understanding of the data context — do not copy
      the raw column name. E.g. {"n_30_39": "Ages 30–39", "pct_employed": "Employment Rate (%)"}.
    - For multi-series bar/line charts, list all series column names in y_keys.

    Rules:
    - Do NOT fabricate statistics — only report numbers returned by tools.
    - key_findings must be specific and quantitative (cite exact numbers from tool results).
    - summary must directly answer the user's query in 2-4 sentences.
    - chart_configs[*].data must be the computed rows from tool results, not raw unified_rows.
    - Always call compute_statistics before drawing any conclusion about a numeric column.
    - Always call group_and_aggregate before a pie or grouped bar chart.
    """,
    output_type=AnalysisResult,
    deps_type=AnalysisDeps,
)


def _numeric_values(rows: list[dict], column: str) -> list[float]:
    return [
        float(row[column])
        for row in rows
        if column in row and isinstance(row[column], (int, float)) and not math.isnan(float(row[column]))
    ]


@analysis_agent.tool(retries=3)
def compute_statistics(ctx: RunContext[AnalysisDeps], column: str) -> dict:
    """
    Compute descriptive statistics for a single numeric column across all unified rows.
    Returns min, max, mean, median, std_dev, q1, q3, and count.
    Call this first to understand a column before drawing conclusions.
    """
    with logfire.span("compute_statistics", column=column):
        if column not in ctx.deps.columns:
            raise ModelRetry(
                f"Column '{column}' not found. Available columns: {ctx.deps.columns}"
            )

        values = _numeric_values(ctx.deps.unified_rows, column)
        if not values:
            raise ModelRetry(
                f"Column '{column}' has no numeric values. "
                "Try a different column or check the data."
            )

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mean = sum(sorted_vals) / n
        median = statistics.median(sorted_vals)
        std_dev = statistics.pstdev(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[(3 * n) // 4]

    logfire.info("compute_statistics complete", column=column, n=n)
    return {
        "column": column,
        "count": n,
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "mean": round(mean, 4),
        "median": median,
        "std_dev": round(std_dev, 4),
        "q1": q1,
        "q3": q3,
    }


@analysis_agent.tool(retries=3)
def rank_values(
    ctx: RunContext[AnalysisDeps],
    sort_column: str,
    top_n: int = 10,
    ascending: bool = False,
) -> dict:
    """
    Return the top or bottom N rows ranked by a numeric column.
    Use to identify leaders, outliers, or extremes relevant to the query.
    Set ascending=True for bottom N (lowest values).
    """
    with logfire.span("rank_values", sort_column=sort_column, top_n=top_n, ascending=ascending):
        if sort_column not in ctx.deps.columns:
            raise ModelRetry(
                f"Column '{sort_column}' not found. Available columns: {ctx.deps.columns}"
            )

        numeric_rows = [
            row for row in ctx.deps.unified_rows
            if isinstance(row.get(sort_column), (int, float))
        ]
        if not numeric_rows:
            raise ModelRetry(
                f"Column '{sort_column}' has no numeric rows to rank."
            )

        ranked = sorted(numeric_rows, key=lambda r: r[sort_column], reverse=not ascending)
        result_rows = ranked[:top_n]

    logfire.info("rank_values complete", sort_column=sort_column, returned=len(result_rows))
    return {
        "sort_column": sort_column,
        "ascending": ascending,
        "top_n": top_n,
        "rows": result_rows,
    }


@analysis_agent.tool(retries=3)
def compute_trend(
    ctx: RunContext[AnalysisDeps],
    x_column: str,
    y_column: str,
) -> dict:
    """
    Detect the linear trend direction and slope for y_column ordered by x_column.
    x_column is typically a year or date column; y_column is a numeric metric.
    Returns slope, direction ("up", "down", or "flat"), and the data points used.
    """
    with logfire.span("compute_trend", x_column=x_column, y_column=y_column):
        for col in (x_column, y_column):
            if col not in ctx.deps.columns:
                raise ModelRetry(
                    f"Column '{col}' not found. Available columns: {ctx.deps.columns}"
                )

        pairs: list[tuple[float, float]] = []
        for row in ctx.deps.unified_rows:
            x_raw = row.get(x_column)
            y_raw = row.get(y_column)
            if x_raw is None or y_raw is None:
                continue
            try:
                x_val = float(str(x_raw).replace(",", "").strip())
                y_val = float(y_raw) if isinstance(y_raw, (int, float)) else None
            except (ValueError, TypeError):
                continue
            if y_val is not None:
                pairs.append((x_val, y_val))

        if len(pairs) < 2:
            raise ModelRetry(
                f"Need at least 2 data points to compute a trend; "
                f"got {len(pairs)} for ({x_column}, {y_column})."
            )

        pairs.sort(key=lambda p: p[0])
        n = len(pairs)
        sum_x = sum(p[0] for p in pairs)
        sum_y = sum(p[1] for p in pairs)
        sum_xy = sum(p[0] * p[1] for p in pairs)
        sum_xx = sum(p[0] ** 2 for p in pairs)

        denom = n * sum_xx - sum_x ** 2
        slope = (n * sum_xy - sum_x * sum_y) / denom if denom != 0 else 0.0

        # Direction threshold: 0.1% of the mean y value
        mean_y = sum_y / n
        threshold = abs(mean_y) * 0.001 if mean_y != 0 else 0.001
        direction = "up" if slope > threshold else ("down" if slope < -threshold else "flat")

        data_points = [{x_column: p[0], y_column: p[1]} for p in pairs]

    logfire.info("compute_trend complete", x_column=x_column, y_column=y_column, direction=direction)
    return {
        "x_column": x_column,
        "y_column": y_column,
        "slope": round(slope, 6),
        "direction": direction,
        "n_points": n,
        "data": data_points,
    }


@analysis_agent.tool(retries=3)
def group_and_aggregate(
    ctx: RunContext[AnalysisDeps],
    group_by_column: str,
    agg_column: str,
    agg_fn: Literal["sum", "avg", "count"],
) -> dict:
    """
    Group rows by a categorical column and compute sum, average, or count of another column.
    Returns a list of {"group": label, "value": number} — directly Recharts-ready for bar/pie charts.
    Use agg_fn="count" when you want to count occurrences of each category regardless of agg_column value.
    """
    with logfire.span("group_and_aggregate", group_by=group_by_column, agg_column=agg_column, agg_fn=agg_fn):
        if group_by_column not in ctx.deps.columns:
            raise ModelRetry(
                f"Column '{group_by_column}' not found. Available columns: {ctx.deps.columns}"
            )
        if agg_fn != "count" and agg_column not in ctx.deps.columns:
            raise ModelRetry(
                f"Column '{agg_column}' not found. Available columns: {ctx.deps.columns}"
            )

        groups: dict[str, list[float]] = {}
        for row in ctx.deps.unified_rows:
            group_key = str(row.get(group_by_column, "unknown"))
            if agg_fn == "count":
                groups.setdefault(group_key, []).append(1.0)
            else:
                val = row.get(agg_column)
                if isinstance(val, (int, float)):
                    groups.setdefault(group_key, []).append(float(val))

        result = []
        for group_key, vals in sorted(groups.items()):
            if agg_fn == "sum":
                value = sum(vals)
            elif agg_fn == "avg":
                value = sum(vals) / len(vals) if vals else 0.0
            else:  # count
                value = float(len(vals))
            result.append({"group": group_key, "value": round(value, 4)})

    logfire.info("group_and_aggregate complete", group_by=group_by_column, n_groups=len(result))
    return {
        "group_by": group_by_column,
        "agg_column": agg_column,
        "agg_fn": agg_fn,
        "result": result,
    }


narrative_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt=(
        "You are a policy data analyst presenting findings to a government stakeholder. "
        "Given a query and structured analysis results, write a clear, flowing response "
        "that directly answers the query. Lead with 2-3 sentences summarising the headline "
        "finding, then present 3-5 specific quantitative bullet points (use • as the bullet). "
        "Be concise and cite exact numbers. Do not use headers or markdown beyond bullet points."
    ),
)


async def stream_narrative(
    analysis_result: AnalysisResult,
    query: str,
) -> AsyncGenerator[str, None]:
    prompt = (
        f"Query: {query}\n\n"
        f"Summary: {analysis_result.summary}\n\n"
        f"Key findings:\n"
        + "\n".join(f"• {f}" for f in analysis_result.key_findings)
    )
    with logfire.span("stream_narrative"):
        async with narrative_agent.run_stream(prompt) as result:
            async for chunk in result.stream_text(delta=True):
                yield chunk


async def run_analysis(
    normalization_result: NormalizationResult,
    enhanced_query: str,
    feedback: str | None = None,
    prior_analyses: list[dict] | None = None,
    research_plan: ResearchPlan | None = None,
) -> tuple[AnalysisResult, list]:
    payload = json.dumps(normalization_result.model_dump(), indent=2)

    prior_block = ""
    if prior_analyses:
        lines = ["=== Prior Analyses in This Conversation ==="]
        for i, pa in enumerate(prior_analyses, 1):
            lines.append(f"Query {i}: \"{pa.get('enhanced_query', '')}\"")
            if pa.get("summary"):
                lines.append(f"Summary: {pa['summary']}")
            if pa.get("key_findings"):
                for kf in pa["key_findings"]:
                    lines.append(f"  - {kf}")
        lines.append("\nBuild on these findings where relevant. Do not repeat what was already established.")
        lines.append("=== End Prior Analyses ===\n")
        prior_block = "\n".join(lines) + "\n"

    feedback_block = ""
    if feedback:
        feedback_block = (
            f"\nPREVIOUS ANALYSIS FEEDBACK (address these issues in this run):\n{feedback}\n"
        )

    plan_block = ""
    if research_plan:
        plan_block = (
            f"Research plan:\n"
            f"- Analysis type: {research_plan.analysis_type}\n"
            f"- Sub-questions to answer:\n"
            + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(research_plan.sub_questions))
            + f"\n- Key metrics to focus on: {', '.join(research_plan.key_metrics)}\n"
            f"- Suggested chart types: {', '.join(research_plan.suggested_chart_types)}\n\n"
        )

    prompt = (
        f"{prior_block}"
        f"Original query: {enhanced_query}\n\n"
        f"{plan_block}"
        f"{feedback_block}"
        f"Unified dataset from normalization:\n{payload}"
    )

    with logfire.span("analysis_agent", n_rows=len(normalization_result.unified_rows)):
        result = await analysis_agent.run(
            prompt,
            deps=AnalysisDeps(
                unified_rows=normalization_result.unified_rows,
                columns=normalization_result.columns,
                query=enhanced_query,
            ),
        )

    logfire.info(
        "analysis complete",
        n_findings=len(result.output.key_findings),
        n_charts=len(result.output.chart_configs),
    )
    return result.output, result.all_messages()


analysis_validation_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a quality reviewer for a data analytics pipeline.

    Given an enhanced query and a completed AnalysisResult (summary, key_findings, chart_configs),
    decide whether the analysis actually answers the query.

    Validation criteria:
    1. QUERY ANSWER: does the summary directly and specifically address what was asked?
    2. QUANTITATIVE FINDINGS: are key_findings specific and numeric (cite actual numbers),
       not vague statements?
    3. CHART APPROPRIATENESS: are the chart types suitable for the data and query type?
       (trend query → line/area, comparison → bar, composition → pie)
    4. COMPLETENESS: are there at least 3 key_findings and at least 2 chart_configs?
    5. DATA SUFFICIENCY: does the analysis reference only a very small number of data points
       (e.g. fewer than 5 data points cited, a single time period, one category) suggesting
       the extraction was too narrow or the dataset is genuinely sparse?
    6. DOMAIN COVERAGE: do the findings actually contain the metrics the query asked for?
       (e.g. query asks for trade volume but findings only discuss population counts; query asks
       for employment rates but data shows housing prices — the datasets are clearly mismatched)

    If valid=true: leave feedback empty and do NOT set root_cause.

    If valid=false: set feedback describing exactly what is missing or wrong, then classify
    root_cause using EXACTLY one of these four values:

    - "insufficient_data"  — the analysis references very few rows (fewer than 5 data points
      cited), a single time period, or explicitly notes data was sparse or truncated. The right
      datasets were probably chosen but extraction was too narrow or had overly strict filters.
      Use this when the datasets seem correct but not enough rows came through.

    - "wrong_datasets"     — the key_findings or summary show that the selected datasets do not
      contain the metric type the query requires (e.g. query asks for trade metrics but findings
      discuss population counts; query asks for employment rates but data shows housing prices).
      Use this only when the datasets are clearly mismatched to the query domain.

    - "poor_synthesis"     — data appears sufficient and relevant but the summary is vague,
      key_findings lack numbers, findings don't address the query's sub-questions, or the
      summary doesn't answer what was asked. The problem is analytical quality, not data quality.

    - "chart_quality"      — the only issue is with charts: wrong chart type for the analysis,
      fewer than 2 charts, or chart keys don't match the data. Use this only when summary and
      key_findings are acceptable but charts are the sole problem.

    Priority order when multiple issues exist:
    wrong_datasets > insufficient_data > poor_synthesis > chart_quality

    Do NOT fail for minor stylistic issues — only for substantive analytical gaps.
    """,
    output_type=AnalysisValidationOutput,
)


async def validate_analysis(
    analysis_result: AnalysisResult,
    enhanced_query: str,
) -> AnalysisValidationOutput:
    prompt = (
        f"Enhanced query: {enhanced_query}\n\n"
        f"Analysis result:\n{analysis_result.model_dump_json(indent=2)}"
    )
    with logfire.span("analysis validation", query=enhanced_query):
        result = await analysis_validation_agent.run(prompt)

    if result.output.valid:
        logfire.info("analysis validated", valid=True)
    else:
        logfire.info("analysis validation failed", valid=False, feedback=result.output.feedback)

    return result.output

import json
from dataclasses import dataclass

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext

from app.schemas.query import ExtractionResult, NormalizationResult
from app.services.llm import get_llm_model_with_fallback


@dataclass
class NormalizationDeps:
    extraction_results: list[ExtractionResult]


normalization_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a data normalization specialist. You receive multiple extraction results from
    different datasets covering the same subject across different time periods or sources.

    Your task is to produce a single unified, analysis-ready dataset by:

    1. UNIT NORMALIZATION — detect and reconcile unit differences (e.g. raw counts vs thousands).
       Always convert to raw counts.

    2. COLUMN HARMONIZATION — map different column names for the same concept to a single
       canonical name (e.g. "Number", "Usual_Mode_of_Transport" → "transport_mode").

    3. CATEGORY HARMONIZATION — map equivalent category labels across datasets to a shared
       vocabulary. When one dataset is more granular, aggregate to match the coarser dataset.
       Document every mapping in your notes. For any categorical column appearing in multiple
       sources, call compare_column_domains with the distinct values from each source to
       identify mismatches before harmonizing.

    4. SOURCE TRACKING — every row must include a "year" or "source" column derived from the
       dataset title so rows remain traceable after merging.

    Workflow:
    - Inspect the extraction results provided.
    - For any categorical column that appears in multiple sources, call
      compare_column_domains with the distinct values from each source to identify
      mismatches before harmonizing.
    - Produce your proposed unified_rows and columns.
    - Call validate_unified_rows with your proposed rows and columns.
    - If validate_unified_rows raises an error, fix ALL reported issues and re-call it.
      You MUST NOT produce the final NormalizationResult until validate_unified_rows
      returns valid=true.
    - Only then return the final NormalizationResult.

    Rules:
    - Do NOT invent data or fill gaps with estimates.
    - Do NOT drop rows unless they are true duplicates after harmonization.
    - DO document every transformation applied in the notes field.
    - Output unified_rows as a flat list of dicts with consistent keys matching columns exactly.
    - If any extraction result has truncated=true, note this in your notes field — the
      unified dataset may be incomplete.
    """,
    output_type=NormalizationResult,
    deps_type=NormalizationDeps,
)


@normalization_agent.tool(retries=3)
def validate_unified_rows(
    _ctx: RunContext[NormalizationDeps],
    rows: list[dict],
    columns: list[str],
) -> dict:
    """
    Validate proposed unified rows before finalising output.
    Call this after producing your unified_rows to check for structural issues.
    Fix any reported problems and re-validate until valid=true.
    """
    if not rows:
        raise ModelRetry(
            "unified_rows is empty — produce rows before calling validate_unified_rows."
        )

    issues = []
    expected = set(columns)

    # Column presence check
    for i, row in enumerate(rows):
        actual = set(row.keys())
        missing = expected - actual
        extra = actual - expected
        if missing:
            issues.append(f"Row {i}: missing columns {sorted(missing)}")
        if extra:
            issues.append(f"Row {i}: unexpected columns {sorted(extra)}")

    # Type consistency check
    numeric_cols = {
        col for col in columns
        if isinstance(rows[0].get(col), (int, float))
    }
    for i, row in enumerate(rows):
        for col in numeric_cols:
            val = row.get(col)
            if val is not None and not isinstance(val, (int, float)):
                issues.append(
                    f"Row {i}, column '{col}': expected numeric, got {type(val).__name__} ({val!r})"
                )

    # Source tracking check
    source_cols = [c for c in columns if c in ("year", "source", "dataset")]
    if not source_cols:
        issues.append(
            "No source tracking column found — add 'year', 'source', or 'dataset' to every row"
        )

    # Null value check
    for i, row in enumerate(rows):
        for col in columns:
            if row.get(col) is None:
                issues.append(
                    f"Row {i}, column '{col}': value is null — ensure no row has missing values in canonical columns"
                )

    # Negative count check
    count_like_cols = {
        col for col in numeric_cols
        if any(kw in col.lower() for kw in ("count", "number", "total", "n_", "num"))
    }
    for i, row in enumerate(rows):
        for col in count_like_cols:
            val = row.get(col)
            if isinstance(val, (int, float)) and val < 0:
                issues.append(
                    f"Row {i}, column '{col}': negative count {val} — counts must be non-negative"
                )

    # 1000x inter-source magnitude jump detection
    if source_cols:
        source_col = source_cols[0]
        for num_col in numeric_cols:
            source_averages: dict[str, list] = {}
            for row in rows:
                src = str(row.get(source_col, "unknown"))
                val = row.get(num_col)
                if isinstance(val, (int, float)):
                    source_averages.setdefault(src, []).append(val)

            avg_by_source = {
                src: sum(vals) / len(vals)
                for src, vals in source_averages.items()
                if vals
            }

            if len(avg_by_source) >= 2:
                averages = list(avg_by_source.values())
                max_avg = max(averages)
                min_avg = min(averages)
                if min_avg > 0 and max_avg / min_avg >= 1000:
                    sources_str = ", ".join(
                        f"{src}={avg:.1f}" for src, avg in avg_by_source.items()
                    )
                    issues.append(
                        f"Column '{num_col}': 1000x magnitude difference detected across sources "
                        f"({sources_str}) — likely a unit mismatch (e.g. raw counts vs thousands). "
                        "Normalise to raw counts."
                    )

    if issues:
        formatted = "\n".join(f"  - {issue}" for issue in issues)
        raise ModelRetry(
            f"validate_unified_rows found {len(issues)} issue(s):\n{formatted}\n\n"
            "Fix all issues and call validate_unified_rows again."
        )

    return {
        "valid": True,
        "total_rows": len(rows),
        "columns_checked": sorted(columns),
        "numeric_columns_detected": sorted(numeric_cols),
        "issues": [],
    }


@normalization_agent.tool
def compare_column_domains(
    _ctx: RunContext[NormalizationDeps],
    col_a_values: list,
    col_b_values: list,
    col_a_label: str = "source_a",
    col_b_label: str = "source_b",
) -> dict:
    """
    Compare two lists of categorical values from different datasets.
    Returns overlap, values only in source A, values only in source B, and Jaccard similarity.
    Use this before deciding how to harmonize category labels across datasets.
    Comparison is case-insensitive and strips leading/trailing whitespace.
    """
    def normalise(v) -> str:
        return str(v).strip().lower()

    set_a = {normalise(v): v for v in col_a_values}
    set_b = {normalise(v): v for v in col_b_values}

    keys_a = set(set_a.keys())
    keys_b = set(set_b.keys())

    overlap_keys = keys_a & keys_b
    only_a_keys = keys_a - keys_b
    only_b_keys = keys_b - keys_a

    return {
        "overlap": sorted([set_a[k] for k in overlap_keys]),
        f"only_in_{col_a_label}": sorted([set_a[k] for k in only_a_keys]),
        f"only_in_{col_b_label}": sorted([set_b[k] for k in only_b_keys]),
        "overlap_count": len(overlap_keys),
        "jaccard_similarity": (
            len(overlap_keys) / len(keys_a | keys_b) if (keys_a | keys_b) else 1.0
        ),
    }


async def run_normalization(
    extraction_results: list[ExtractionResult],
    enhanced_query: str,
) -> tuple[NormalizationResult, list]:
    payload = json.dumps(
        [r.model_dump() for r in extraction_results],
        indent=2,
    )
    prompt = (
        f"Original query: {enhanced_query}\n\n"
        f"Extraction results from {len(extraction_results)} dataset(s):\n{payload}"
    )

    with logfire.span("normalization_agent", n_sources=len(extraction_results)):
        result = await normalization_agent.run(
            prompt,
            deps=NormalizationDeps(extraction_results=extraction_results),
        )

    logfire.info(
        "normalization complete",
        n_unified_rows=len(result.output.unified_rows),
        columns=result.output.columns,
    )

    return result.output, result.all_messages()

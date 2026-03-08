from pydantic_ai import Agent

from app.schemas.query import (
    DatasetSelectionOutput,
    DatasetValidationOutput,
    IntentAnalysis,
    ResearchPlan,
)
from app.services.llm import get_llm_model_with_fallback

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

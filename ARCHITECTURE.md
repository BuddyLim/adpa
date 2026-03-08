# Architecture

## System Overview

```
Browser (TanStack Start / React)
        |
        | HTTP POST /query
        v
FastAPI Backend
        |
        |-- Spawns background task
        |
        v
CoordinatorGraph (pydantic-graph FSM)
        |
        |-- Streams SSE events --> GET /query/{id}/stream --> Browser
        |
        v
SQLite / PostgreSQL  (pipeline state, results, conversation history)
        |
DuckDB (in-process SQL over CSV datasets)
```

---

## FSM Pipeline

The pipeline is a directed graph of 9 nodes. Each node runs an LLM agent or a deterministic step, updates shared `CoordinatorState`, then routes to the next node.

```
LoadContext
    |
    v
AnalyzeIntent ----[infeasible]----> End (rejected)
    |
    v [feasible]
SelectDatasets <-----------------------------+
    |                                        |
    v                                        |
ValidateDatasetPlan --[invalid, retry < 2]--+
    |
    v [valid]
PlanResearch <-------------------------------+
    |                                        |
    v                                        |
Extract (parallel per dataset)               |
    |                                        |
    v                                        |
Normalize                                    |
    |                                        |
    v                                        |
Analyze                                      |
    |                                        |
    v                                        |
ValidateAnalysis --[low quality, retry < 2]--+
    |
    v [pass]
End (completed)
```

**Backward feedback loops:**

- `ValidateAnalysisNode` can route back to `SelectDatasetsNode` (if datasets were likely wrong) or to `PlanResearchNode` (if the research plan needs refinement). Up to 2 backward re-entries (`pipeline_iterations`) are allowed before the run completes with whatever result exists.

---

## Node Descriptions

| Node                      | Agent                     | Purpose                                                                              |
| ------------------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| `LoadContextNode`         | None (DB read)            | Loads available dataset catalogue and conversation history from the database         |
| `AnalyzeIntentNode`       | `intent_agent`            | Classifies query feasibility, identifies policy domain, enhances the raw query       |
| `SelectDatasetsNode`      | `dataset_selector_agent`  | Selects 1-3 datasets from the catalogue that can answer the query                    |
| `ValidateDatasetPlanNode` | `dataset_validator_agent` | Validates the selected datasets cover the query dimensions; sends feedback if not    |
| `PlanResearchNode`        | `research_planner_agent`  | Produces a structured research plan (analysis type, sub-questions, extraction hints) |
| `ExtractNode`             | `extraction_agent`        | Runs DuckDB SQL against each selected dataset in parallel; produces structured rows  |
| `NormalizeNode`           | `normalization_agent`     | Merges and reconciles extraction results into a unified column schema                |
| `AnalyzeNode`             | `analysis_agent`          | Generates key findings, summary, and chart configurations from the normalized data   |
| `ValidateAnalysisNode`    | LLM judge                 | Scores analysis quality and routes backward if below threshold                       |

---

## Agent Reference

### intent_agent

**Goal:** Gate queries and enrich the raw question before any data access occurs.

**Inputs:** raw user query + optional conversation history

**Output:** `IntentAnalysis` (is_feasible, domain, enhanced_query, rejection_reason, is_followup, suggested_prior_datasets)

**Behaviour:**

- Rejects queries that are off-domain (weather, jokes, personal data), ask for real-time information, or are too vague to map to any data dimension (e.g. "Tell me about Singapore").
- For accepted queries it rewrites the raw question into a 2-4 sentence analytical framing that names the analysis type (trend, comparison, ranking, distribution, correlation) and any relevant dimensions.
- Detects follow-up queries and surfaces which datasets were used previously so downstream nodes can reuse them.

---

### dataset_selector_agent

**Goal:** Map the enhanced query to 1-3 datasets from the catalogue.

**Inputs:** enhanced query, domain, full dataset catalogue

**Output:** `DatasetSelectionOutput` (selected_datasets, cannot_answer, reason)

**Behaviour:**

- Only selects datasets whose title or description genuinely overlaps the query domain.
- For multi-dataset queries, checks that selected datasets share joinable key columns.
- For follow-up queries, prefers datasets used in prior runs unless there is a strong reason to switch.
- If no dataset is relevant, sets `cannot_answer=true` with a clear explanation rather than guessing.

---

### dataset_validator_agent

**Goal:** Independently verify that the chosen datasets can actually answer the query before any SQL runs.

**Inputs:** enhanced query, proposed dataset selection

**Output:** `DatasetValidationOutput` (valid, confirmation_reason, feedback)

**Behaviour:**

- Checks three criteria: coverage (do descriptions suggest the right data dimensions?), sufficiency (are enough datasets selected for the analysis type?), and relevance (are any selections clearly off-topic?).
- If `valid=false`, writes structured feedback describing what is missing. `SelectDatasetsNode` passes this feedback back into the selector on retry (up to 2 times).

---

### research_planner_agent

**Goal:** Produce a structured research plan that guides extraction and analysis.

**Inputs:** enhanced query, domain, validated dataset selection
**Output:** `ResearchPlan` (analysis_type, sub_questions, key_metrics, extraction_hints, suggested_chart_types)

**Behaviour:**

- Classifies the analysis type: `trend`, `comparison`, `ranking`, `distribution`, or `correlation`.
- Writes 2-4 concrete sub-questions that together fully answer the user's query.
- Produces per-dataset `extraction_hints` (one sentence each) specifying which columns, filters, time ranges, or categories the extraction agent should prioritise.
- Suggests 2-3 chart types appropriate for the analysis type (line for trends, bar for comparisons, pie for distributions).

---

### extraction_agent

**Goal:** Run SQL against a single CSV dataset via DuckDB and return structured rows.

**Inputs:** enhanced query, research plan, dataset file path, peer dataset schemas (for join alignment)

**Output:** `ExtractionResult` (rows, columns, join_keys, sql_query, summary, truncated)

**Behaviour:**

- Each dataset is extracted in a separate agent run; all runs for a query execute in parallel (`asyncio.gather`).
- Receives peer schemas so it can align column names and apply consistent filters across datasets before results are merged by the normalizer.
- Results are capped at 500 rows. If `truncated=true` the agent is instructed to tighten filters and re-run.
- Only task is to extract and not analyze data

**Tools:**

| Tool                | Description                                                                                                                                                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load_dataset`      | Loads the CSV into a DuckDB view named `dataset` and returns schema + 3 sample rows                                                                                                                                               |
| `get_unique_values` | Returns distinct values for a text column; must be called before any categorical WHERE filter                                                                                                                                     |
| `describe_column`   | Returns min, max, mean, and null count for a numeric or date column                                                                                                                                                               |
| `count_rows`        | Executes a COUNT SQL to check result size before fetching                                                                                                                                                                         |
| `execute_query`     | Runs a SELECT against `dataset` and returns up to 500 rows                                                                                                                                                                        |
| `ask_clarification` | Records an assumption when a query is genuinely ambiguous, then proceeds <br> (Marked, but not used in the FSM, potential extension where we can interrupt the FSM to ask user for clarifying questions supported by pydantic-ai) |

---

### normalization_agent

**Goal:** Merge multiple extraction results into a single, analysis-ready unified dataset.

**Inputs:** all `ExtractionResult` objects for the current pipeline run, enhanced query

**Output:** `NormalizationResult` (unified_rows, columns, notes)

**Behaviour:**

- Performs four transformation steps in order: unit normalization (e.g. thousands to raw counts), column harmonization (maps synonymous column names to a single canonical name), category harmonization (aligns label vocabularies across datasets), and source tracking (ensures every row carries a `year` or `source` column).
- Uses `compare_column_domains` to inspect Jaccard similarity between categorical vocabularies before deciding how to align them.
- Uses `validate_unified_rows` as a gating check: the agent must call this tool and fix all reported issues before it can emit a final `NormalizationResult`. The tool enforces column consistency, type consistency, source tracking, null-free rows, non-negative counts, and absence of 1000x magnitude jumps between sources.

**Tools:**

| Tool                     | Description                                                                                                                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compare_column_domains` | Compares two lists of categorical values (case-insensitive) and returns overlap, Jaccard similarity, and values unique to each source                                                        |
| `validate_unified_rows`  | Validates proposed unified rows for column completeness, type consistency, source tracking, nulls, negative counts, and unit magnitude jumps; raises `ModelRetry` until all issues are fixed |

---

### analysis_agent

**Goal:** Derive quantitative findings and chart-ready configurations from the unified dataset.

**Inputs:** unified rows + columns, enhanced query, research plan, optional feedback from a prior failed validation
**Output:** `AnalysisResult` (summary, key_findings, chart_configs)

**Behaviour:**

- Follows a four-step workflow: explore (statistics), rank (identify leaders/outliers), trend (linear regression over time), group (aggregate by category), then synthesise findings.
- Produces exactly 2-3 `ChartConfig` objects with `data` taken directly from tool results (not raw unified rows), correct axis keys, and human-readable labels.
- key_findings must be specific and cite exact numbers returned by tools; vague findings will be flagged by `analysis_validation_agent`.
- Receives prior analyses from the same conversation so it can build on previous findings rather than repeat them.

**Tools:**

| Tool                  | Description                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------- |
| `compute_statistics`  | Computes min, max, mean, median, std_dev, Q1, Q3 for a numeric column                                       |
| `rank_values`         | Returns top or bottom N rows sorted by a numeric column                                                     |
| `compute_trend`       | Computes linear regression slope and direction ("up", "down", "flat") for a y-column ordered by an x-column |
| `group_and_aggregate` | Groups rows by a categorical column and computes sum, avg, or count; output is Recharts-ready               |

---

### analysis_validation_agent

**Goal:** Quality-gate the analysis output and classify the root cause of any failure.

**Inputs:** enhanced query, completed `AnalysisResult`
**Output:** `AnalysisValidationOutput` (valid, feedback, root_cause)

**Behaviour:**

- Checks six criteria: query answer (does the summary directly address the question?), quantitative findings (do key_findings cite actual numbers?), chart appropriateness, completeness (at least 3 findings, at least 2 charts), data sufficiency, and domain coverage.
- If `valid=false`, classifies the failure using exactly one of four root causes:
  - `wrong_datasets` - selected datasets do not contain the required metric type
  - `insufficient_data` - datasets are correct but extraction returned too few rows
  - `poor_synthesis` - data is sufficient but the analysis is vague or off-topic
  - `chart_quality` - summary and findings are acceptable but charts are the sole problem
- `ValidateAnalysisNode` uses the root cause to decide whether to route back to `SelectDatasetsNode` (wrong_datasets) or `PlanResearchNode` (insufficient_data or poor_synthesis).
- Only fails for substantive analytical gaps; minor stylistic issues pass.

---

## API Layer

| Endpoint                       | Method | Description                                                                                |
| ------------------------------ | ------ | ------------------------------------------------------------------------------------------ |
| `/query`                       | POST   | Accepts a question and optional `conversation_id`; returns `task_id` and `conversation_id` |
| `/query/{id}/stream`           | GET    | SSE stream for real-time pipeline progress events                                          |
| `/conversations/{id}/results`  | GET    | Returns all completed pipeline runs with analysis results for a conversation               |
| `/conversations/{id}/messages` | GET    | Returns all user and assistant messages for a conversation                                 |

---

## SSE Event Types

All events are serialized as JSON and sent over the SSE stream.

| Event Type        | Payload                       | Description                                                 |
| ----------------- | ----------------------------- | ----------------------------------------------------------- |
| `StatusEvent`     | `stage`, `message`            | Node lifecycle update (e.g., "Extracting data...")          |
| `ToolCallEvent`   | `tool_name`, `args`           | Fired when an agent calls a DuckDB tool                     |
| `ToolResultEvent` | `tool_name`, `result_summary` | Fired when a tool call completes                            |
| `ErrorEvent`      | `stage`, `message`            | Fired on unrecoverable errors                               |
| `ResultEvent`     | Full `AnalysisResult`         | Final event containing findings, summary, and chart configs |

---

## Database Schema

10 tables managed by SQLAlchemy + Alembic:

| Table                   | Purpose                                                         |
| ----------------------- | --------------------------------------------------------------- |
| `users`                 | User identity (UUID, created_at)                                |
| `conversations`         | Groups pipeline runs under a single chat thread                 |
| `messages`              | User and assistant messages within a conversation               |
| `pipeline_runs`         | One record per query execution (status, enhanced_query, timing) |
| `pipeline_steps`        | Ordered log of status messages produced during a run            |
| `datasets`              | Catalogue of available CSV datasets (title, file_path, summary) |
| `pipeline_run_datasets` | Many-to-many join: which datasets were used in a run            |
| `extraction_results`    | Per-dataset SQL results stored as JSON rows                     |
| `normalization_results` | Merged unified rows and column list after normalization         |
| `analysis_results`      | Final summary, key_findings, and chart_configs JSON             |

**Relationships:**

```
User
 └── Conversation (1:N)
      ├── Message (1:N)
      │    └── PipelineRun (1:1, the triggering message)
      └── PipelineRun (1:N, denormalized FK)
           ├── PipelineStep (1:N)
           ├── Dataset (N:M via pipeline_run_datasets)
           ├── ExtractionResultRecord (1:N)
           ├── NormalizationResultRecord (1:1)
           └── AnalysisResultRecord (1:1)
```

---

## Frontend Architecture

- **Framework:** TanStack Start (React 19, SSR, file-based routing)
- **Data fetching:** TanStack React Query with custom hooks for SSE consumption
- **Visualizations:** Recharts (bar, line, area, pie charts driven by `chart_configs` from the API)
- **Styling:** Tailwind CSS v4
- **Key routes:**
  - `/` - conversation list and new query input
  - `/conversations/:id` - message thread with streaming results panel and chart visualizations

---

## Key Design Decisions

**FSM over a linear pipeline**
A linear pipeline cannot recover from partial failures or route conditionally. The FSM lets `ValidateAnalysisNode` retry upstream nodes with structured feedback, improving output quality without a full restart.

**DuckDB for dataset queries**
CSV datasets are queried in-process with DuckDB. This eliminates an ETL step, keeps the deployment simple (no separate data warehouse), and supports full SQL including joins across multiple files.

**pydantic-ai for agent I/O**
Every agent declares a structured `output_type` (a Pydantic model). This eliminates string parsing, provides automatic validation, and makes agent contracts explicit and testable.

**SSE for real-time progress**
Queries can take 20-60 seconds end-to-end. SSE pushes node-level status events, tool calls, and tool results to the browser incrementally so users see progress rather than a blank loading state.

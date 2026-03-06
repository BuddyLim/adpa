import duckdb
import json
from dataclasses import dataclass, field

import logfire
from pydantic_ai import Agent, ModelRetry, RunContext

from app.schemas.query import ExtractionResult
from app.services.llm import get_llm_model_with_fallback

EXECUTE_QUERY_ROW_LIMIT = 500


@dataclass
class PeerSchema:
    title: str
    columns: list[dict]  # [{"name": ..., "type": ...}]
    sample_rows: list[dict]


@dataclass
class ExtractionDeps:
    dataset_path: str
    dataset_title: str
    peer_schemas: list[PeerSchema] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)
    _con: duckdb.DuckDBPyConnection | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> "ExtractionDeps":
        self._con = duckdb.connect()
        self._con.execute(
            f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto('{self.dataset_path}')"
        )
        return self

    def __exit__(self, *_) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            raise RuntimeError("ExtractionDeps must be used as a context manager")
        return self._con


extraction_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt=f"""
    You are a data extraction specialist. Extract the rows and columns most relevant
    to the user's analytical query from a dataset.

    Available tools:
    - load_dataset: inspect schema and sample rows. Call this first.
    - get_unique_values(column): get distinct values for any text column you plan to filter
      on. Always call this before writing a WHERE clause on a categorical column — never
      guess values from sample rows alone.
    - describe_column(column): get min, max, mean, and null count for a column. Use this
      when the query uses relative terms like "recent", "high", or "top N%" to understand
      the data range before deciding on a filter threshold.
    - count_rows(sql): check result size before fetching. Use when the result may be large.
    - execute_query(sql): run your final SELECT against the 'dataset' view. Results are
      capped at {EXECUTE_QUERY_ROW_LIMIT} rows. If truncated=true, tighten your filter
      and re-run with a more specific WHERE clause.
    - ask_clarification(question): if the query is genuinely ambiguous in a way that changes
      which data to extract, record your assumption and proceed with your best interpretation.

    If other datasets are being extracted in parallel (peer_schemas in your deps), their
    schemas and sample rows are provided in the run prompt. Use them to:
    - Choose column names and types that align with what peer datasets expose.
    - Propose join_keys that exist (or can be derived) in both your dataset and the peers.
    - Apply consistent filters so all extractions cover the same scope (e.g. same years,
      same categories) unless the query explicitly asks otherwise.

    Rules:
    - Do NOT interpret trends, draw conclusions, or give policy recommendations.
    - Do NOT return all rows — filter to what is directly relevant.
    - Do NOT speculate about column meanings beyond what the schema shows.
    - Do NOT guess categorical values; always call get_unique_values first.
    - If no rows match, return an empty list with a summary explaining why.
    - If execute_query returns truncated=true, tighten your filter and re-run.
    """,
    output_type=ExtractionResult,
    deps_type=ExtractionDeps,
)


def load_schema(path: str, title: str) -> PeerSchema:
    """Load schema and sample rows for a dataset without a full agent run."""
    with duckdb.connect() as con:
        con.execute(f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto('{path}')")
        schema_rows = con.execute("DESCRIBE SELECT * FROM dataset LIMIT 0").fetchall()
        columns = [{"name": r[0], "type": r[1]} for r in schema_rows]
        sample = json.loads(
            con.execute("SELECT * FROM dataset LIMIT 3").fetchdf().to_json(orient="records")
        )
    return PeerSchema(title=title, columns=columns, sample_rows=sample)


@extraction_agent.tool
def load_dataset(ctx: RunContext[ExtractionDeps]) -> dict:
    """
    Inspect the dataset schema: returns column names, inferred types, and 3 sample rows.
    Call this first before writing any SQL.
    """
    dataset = ctx.deps.dataset_title

    with logfire.span("load_dataset", dataset=dataset):
        try:
            schema_rows = ctx.deps.con.execute(
                "DESCRIBE SELECT * FROM dataset LIMIT 0"
            ).fetchall()
            columns = [{"name": r[0], "type": r[1]} for r in schema_rows]

            sample = json.loads(
                ctx.deps.con.execute("SELECT * FROM dataset LIMIT 3")
                .fetchdf()
                .to_json(orient="records")
            )
        except duckdb.Error as exc:
            logfire.error("load_dataset failed", dataset=dataset, error=str(exc), exc_info=True)
            raise

    logfire.info("dataset loaded", dataset=dataset, column_count=len(columns))
    return {
        "dataset_title": dataset,
        "columns": columns,
        "sample_rows": sample,
    }


@extraction_agent.tool(retries=3)
def get_unique_values(ctx: RunContext[ExtractionDeps], column: str) -> dict:
    """
    Return distinct values for a single column. Use before filtering on any text/categorical
    column — do NOT guess category names from sample rows alone.
    """
    dataset = ctx.deps.dataset_title

    with logfire.span("get_unique_values", dataset=dataset, column=column):
        try:
            rows = ctx.deps.con.execute(
                f"SELECT DISTINCT {column} FROM dataset ORDER BY 1"
            ).fetchall()
            values = [r[0] for r in rows]
        except duckdb.Error as exc:
            logfire.error(
                "get_unique_values failed",
                dataset=dataset,
                column=column,
                error=str(exc),
                exc_info=True,
            )
            raise ModelRetry(
                f"Could not retrieve distinct values for column '{column}': {exc}"
            ) from exc

    logfire.info("get_unique_values complete", dataset=dataset, column=column, n_values=len(values))
    return {"column": column, "distinct_values": values, "count": len(values)}


@extraction_agent.tool(retries=3)
def describe_column(ctx: RunContext[ExtractionDeps], column: str) -> dict:
    """
    Return min, max, mean, and null_count for a column. Use for numeric or date columns
    when the query uses relative terms (e.g. "recent", "top 10%") to understand the
    data range before writing a filter threshold.
    """
    dataset = ctx.deps.dataset_title

    with logfire.span("describe_column", dataset=dataset, column=column):
        try:
            row = ctx.deps.con.execute(
                f"""
                SELECT
                    MIN({column}),
                    MAX({column}),
                    AVG({column}),
                    COUNT(*) FILTER (WHERE {column} IS NULL)
                FROM dataset
                """
            ).fetchone()
        except duckdb.Error as exc:
            logfire.error(
                "describe_column failed",
                dataset=dataset,
                column=column,
                error=str(exc),
                exc_info=True,
            )
            raise ModelRetry(f"Could not describe column '{column}': {exc}") from exc

    logfire.info("describe_column complete", dataset=dataset, column=column)

    if(row is None):
       return {
            "column": column,
            "min": None,
            "max": None,
            "mean": None,
            "null_count": None,
        }

    return {
        "column": column,
        "min": row[0],
        "max": row[1],
        "mean": row[2],
        "null_count": row[3],
    }


@extraction_agent.tool(retries=3)
def count_rows(ctx: RunContext[ExtractionDeps], sql: str) -> dict:
    """
    Run a COUNT(*) on your intended SELECT to verify row count before fetching.
    Write the full SELECT as you would pass to execute_query; this tool wraps it in
    SELECT COUNT(*) FROM (...) automatically.
    The only available table is the view named 'dataset'.
    """
    dataset = ctx.deps.dataset_title

    with logfire.span("count_rows", dataset=dataset, sql=sql):
        try:
            row = ctx.deps.con.execute(
                f"SELECT COUNT(*) FROM ({sql}) AS _subq"
            ).fetchone()
            count = row[0] if row is not None else 0
        except duckdb.Error as exc:
            logfire.error(
                "count_rows failed", dataset=dataset, sql=sql, error=str(exc), exc_info=True
            )
            raise ModelRetry(
                f"COUNT query failed: {exc}\n"
                "The only available table is the view named 'dataset'."
            ) from exc

    logfire.info("count_rows complete", dataset=dataset, count=count)
    return {"count": count, "sql_used": sql}


@extraction_agent.tool(retries=3)
def execute_query(ctx: RunContext[ExtractionDeps], sql: str) -> dict:
    """
    Execute a DuckDB SQL SELECT against the 'dataset' view.
    Only return columns and rows relevant to the user's query.
    Results are capped at 500 rows. If truncated=true is returned, tighten your
    WHERE clause and re-run with a more specific filter.
    """
    dataset = ctx.deps.dataset_title
    retry_num = ctx.retry

    if "LIMIT" not in sql.upper():
        guarded_sql = f"SELECT * FROM ({sql}) AS _guarded LIMIT {EXECUTE_QUERY_ROW_LIMIT}"
    else:
        guarded_sql = sql

    with logfire.span("execute_query", dataset=dataset, sql=guarded_sql, attempt=retry_num + 1):
        try:
            df = ctx.deps.con.execute(guarded_sql).fetchdf()
            rows = json.loads(df.to_json(orient="records"))
        except duckdb.Error as exc:
            logfire.error(
                "execute_query failed",
                dataset=dataset,
                sql=guarded_sql,
                attempt=retry_num + 1,
                error=str(exc),
                exc_info=True,
            )
            raise ModelRetry(
                f"SQL execution failed: {exc}\n"
                "The only available table is the view named 'dataset'."
            ) from exc

    truncated = len(rows) == EXECUTE_QUERY_ROW_LIMIT

    logfire.info(
        "extraction query executed",
        dataset=dataset,
        sql=guarded_sql,
        attempt=retry_num + 1,
        row_count=len(rows),
        truncated=truncated,
    )

    return {
        "rows": rows,
        "row_count": len(rows),
        "columns": list(df.columns),
        "truncated": truncated,
    }


@extraction_agent.tool
def ask_clarification(ctx: RunContext[ExtractionDeps], question: str) -> dict:
    """
    Record an ambiguity in the query along with your intended assumption.
    Proceed with your best interpretation and include the assumption in the summary.
    """
    ctx.deps.clarifications.append(question)
    logfire.info(
        "clarification recorded", dataset=ctx.deps.dataset_title, question=question
    )
    return {
        "recorded": True,
        "instruction": (
            "Clarification noted. Proceed with your best interpretation and include "
            "your assumption clearly in the extraction summary."
        ),
    }

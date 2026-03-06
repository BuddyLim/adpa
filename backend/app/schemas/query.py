from typing import Annotated, Any, List, Literal, Union

from pydantic import BaseModel, Field, model_validator

from enum import Enum


class MessageType(str, Enum):
    STATUS = "status"
    RESULT = "result"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class CoordinatorDataset(BaseModel):
    title: str
    path: str


class CoordinatorDecision(BaseModel):
    accepted: bool
    reason: str  # always populate — useful for both rejection messages and SSE logs
    enhanced_query: str
    dataset_selected: List[CoordinatorDataset] | None

class ExtractionResult(BaseModel):
    source_dataset: str
    summary: str
    rows: list[dict]
    join_keys: List[str]
    sql_query: str
    truncated: bool = False


class NormalizationResult(BaseModel):
    notes: str  # describes unit conversions, category mappings, column renames applied
    unified_rows: list[dict]
    columns: list[str]  # canonical column names in unified_rows


class ChartConfig(BaseModel):
    chart_type: Literal["bar", "line", "area", "pie"]
    title: str
    description: str  # one-sentence explanation of what this chart shows
    # bar / line / area
    x_key: str | None = None
    y_keys: list[str] = []
    x_label: str | None = None
    y_label: str | None = None
    # Human-readable display names for each series, shown in tooltips and legends.
    # Must cover every key in y_keys, e.g. {"n_30_39": "Ages 30–39"}.
    # Use your understanding of the data context — do not copy the raw column name.
    series_labels: dict[str, str] = {}
    # pie / donut
    name_key: str | None = None
    value_key: str | None = None
    # Recharts-ready data payload — already sliced/grouped by the agent
    data: list[dict]
    color: str | None = None

    @model_validator(mode="after")
    def check_required_keys(self) -> "ChartConfig":
        if self.chart_type in ("bar", "line", "area"):
            missing = []
            if not self.x_key:
                missing.append("x_key")
            if not self.y_keys:
                missing.append("y_keys")
            if missing:
                raise ValueError(
                    f"{self.chart_type} chart requires {missing}. "
                    f"Set them to column names from the data."
                )
            unlabelled = [k for k in self.y_keys if k not in self.series_labels]
            if unlabelled:
                raise ValueError(
                    f"series_labels is missing entries for: {unlabelled}. "
                    "Provide a human-readable display name for every key in y_keys."
                )
        elif self.chart_type == "pie":
            missing = []
            if not self.name_key:
                missing.append("name_key")
            if not self.value_key:
                missing.append("value_key")
            if missing:
                raise ValueError(
                    f"pie chart requires {missing}. "
                    f"Set them to column names from the data."
                )
        return self


class AnalysisResult(BaseModel):
    summary: str               # 2-4 sentence narrative directly answering the query
    key_findings: list[str]    # 3-5 quantitative bullet points citing specific numbers
    chart_configs: list[ChartConfig]  # 2-3 recommended chart visualisations


# ─── SSE wire types ───────────────────────────────────────────────────────────
# One model per message variant, discriminated by `type`.
# pipeline.py yields these; chat.queries.ts mirrors them on the frontend.

class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    accepted: bool
    reason: str
    refined_query: str  # always populated (decision.enhanced_query)


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool: str  # "{agent}/{tool_name}", e.g. "extraction/execute_query"
    args: dict[str, Any]


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool: str  # "{agent}/{tool_name}"
    result: Any


class AnalysisTextEvent(BaseModel):
    type: Literal["analysis_text"] = "analysis_text"
    chunk: str  # streaming text delta from the narrative agent


SSEEvent = Annotated[
    Union[StatusEvent, ResultEvent, ToolCallEvent, ToolResultEvent, AnalysisTextEvent],
    Field(discriminator="type"),
]
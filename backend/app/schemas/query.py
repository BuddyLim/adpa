from typing import Annotated, Any, List, Literal, Union

from pydantic import BaseModel, Field

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


SSEEvent = Annotated[
    Union[StatusEvent, ResultEvent, ToolCallEvent, ToolResultEvent],
    Field(discriminator="type"),
]
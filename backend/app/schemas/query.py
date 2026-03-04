from pydantic import BaseModel

from enum import Enum


class MessageType(str, Enum):
    STATUS = "status"
    RESULT = "result"


class CoordinatorDataset(BaseModel):
    title: str
    path: str


class CoordinatorDecision(BaseModel):
    accepted: bool
    reason: str  # always populate — useful for both rejection messages and SSE logs
    refined_query: str | None = (
        None  # only if accepted — cleaned up version of the user's input
    )
    dataset_selected: CoordinatorDataset | None

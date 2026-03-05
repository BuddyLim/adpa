from typing import List

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
    enhanced_query: str
    dataset_selected: List[CoordinatorDataset] | None

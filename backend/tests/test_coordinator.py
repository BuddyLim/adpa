import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import Agent, models
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, TextPart

from app.schemas.query import CoordinatorDecision
from app.agents.coordinator import CoordinatorDeps, coordinator_agent, list_datasets

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    # All repo methods are async, so mock them as AsyncMock
    repo.list_datasets = AsyncMock(return_value=json.dumps([
        {
            "title": 'dataset-1',
            "summary": 'summary-1',
            "filepath": 'path-1',
        }
    ]))

    return repo


def construct_coordinator_deps(mock_repo):
    return CoordinatorDeps(
        pipeline_repo=mock_repo
    )

def construct_coordinator_run(query: str, agent: Agent[CoordinatorDeps, CoordinatorDecision], mock_repo):
    return agent.run(query, deps=construct_coordinator_deps(mock_repo))

def accept_handler(_messages, _info):
    return ModelResponse(
        parts=[
            TextPart(
                '{"accepted": true, "reason": "Relevant to commuting dataset", '
                '"enhanced_query": "commute mode by age", '
                '"dataset_selected": [{"title": "Commuting Habits ...", "path": "./app/mock_data/...csv"}]}'
            )
        ]
    )


def reject_handler(_messages, _info):
    return ModelResponse(
        parts=[
            TextPart(
                '{"accepted": false, "reason": "Query unrelated to available datasets", '
                '"enhanced_query": "commute mode by age", "dataset_selected": null}'
            )
        ]
    )


def accept_no_dataset_handler(_messages, _info):
    return ModelResponse(
        parts=[
            TextPart(
                '{"accepted": true, "reason": "Query is relevant but no matching dataset found", '
                '"enhanced_query": "commute mode by age", '
                '"dataset_selected": null}'
            )
        ]
    )


async def test_accepted_query(mock_repo):
    with coordinator_agent.override(model=FunctionModel(accept_handler)):
        result = await construct_coordinator_run("How do Singaporeans commute to work?", agent=coordinator_agent, mock_repo=mock_repo)
    decision: CoordinatorDecision = result.output
    assert decision.accepted is True
    assert decision.reason != ""
    assert decision.enhanced_query is not None
    assert decision.dataset_selected is not None
    assert len(decision.dataset_selected) > 0


async def test_rejected_query(mock_repo):
    with coordinator_agent.override(model=FunctionModel(reject_handler)):
        result = await construct_coordinator_run("What is the weather in London?", agent=coordinator_agent, mock_repo=mock_repo)
    decision: CoordinatorDecision = result.output
    assert decision.accepted is False
    assert decision.reason != ""
    assert decision.dataset_selected is None


async def test_accepted_but_no_dataset(mock_repo):
    with coordinator_agent.override(model=FunctionModel(accept_no_dataset_handler)):
        result = await construct_coordinator_run("How do Singaporeans commute to work?", agent=coordinator_agent, mock_repo=mock_repo)
    decision: CoordinatorDecision = result.output
    assert decision.accepted is True
    assert decision.reason != ""
    assert decision.dataset_selected is None


async def test_list_datasets_tool(mock_repo):
    ctx = MagicMock()
    ctx.deps = CoordinatorDeps(pipeline_repo=mock_repo)

    result = await list_datasets(ctx)

    mock_repo.list_datasets.assert_awaited_once()
    assert isinstance(result, str)


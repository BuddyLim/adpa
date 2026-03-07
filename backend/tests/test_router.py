import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.repositories.pipeline import get_pipeline_repo
from app.router.query import router
from app.services.query import get_query_service

pytestmark = pytest.mark.anyio

# Minimal test app — avoids main.py lifespan (migrations, seeding)
router_app = FastAPI()
router_app.include_router(router)


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.initiate = AsyncMock(return_value=("task-1", "conv-1", "My Title"))
    svc.get_producer = MagicMock(return_value=AsyncMock())
    svc.get_stream = MagicMock(return_value=None)
    return svc


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_conversation_results = AsyncMock(return_value=[])
    repo.get_messages = AsyncMock(return_value=[])
    return repo


@pytest.fixture
async def client(mock_service, mock_repo):
    router_app.dependency_overrides[get_query_service] = lambda: mock_service
    router_app.dependency_overrides[get_pipeline_repo] = lambda: mock_repo
    async with AsyncClient(transport=ASGITransport(app=router_app), base_url="http://test") as ac:
        yield ac
    router_app.dependency_overrides.clear()


# ─── POST /query ──────────────────────────────────────────────────────────────

async def test_post_query_happy(client, mock_service):
    response = await client.post("/query", json={"question": "How do people commute?"})

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-1"
    assert body["conversation_id"] == "conv-1"
    assert body["title"] == "My Title"
    mock_service.initiate.assert_awaited_once()


async def test_post_query_conversation_not_found(client, mock_service):
    mock_service.initiate = AsyncMock(side_effect=ValueError("Conversation not found"))

    response = await client.post(
        "/query", json={"question": "hello", "conversation_id": "bad-id"}
    )

    assert response.status_code == 404


# ─── GET /query/{id}/stream ───────────────────────────────────────────────────

async def test_get_stream_happy(client, mock_service):
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put('data: {"type": "status", "message": "Processing..."}\n\n')
    await queue.put(None)  # sentinel to close the stream
    mock_service.get_stream = MagicMock(return_value=queue)

    response = await client.get("/query/task-1/stream")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "Processing" in response.text


async def test_get_stream_not_found(client, mock_service):
    mock_service.get_stream = MagicMock(return_value=None)

    response = await client.get("/query/unknown-task/stream")

    assert response.status_code == 404


# ─── GET /conversations/{id}/results ─────────────────────────────────────────

def _make_mock_run():
    """Return a MagicMock that satisfies the PipelineRunResult mapping in the router."""
    run = MagicMock()
    run.id = "run-1"
    run.status = "completed"
    run.enhanced_query = "commute mode analysis"
    run.created_at = datetime(2024, 1, 1)
    run.completed_at = datetime(2024, 1, 1)
    run.datasets = [MagicMock(id="ds-1", title="Commute Dataset")]
    run.steps = [MagicMock(message="Searching...", step_type="query_analysis", step_order=1)]
    run.extraction_results = []
    run.normalization_result = None
    run.analysis_result = None
    return run


async def test_get_conversation_results_happy(client, mock_repo):
    mock_repo.get_conversation_results = AsyncMock(return_value=[_make_mock_run()])

    response = await client.get("/conversations/conv-1/results")

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conv-1"
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "completed"


async def test_get_conversation_results_not_found(client, mock_repo):
    mock_repo.get_conversation_results = AsyncMock(return_value=[])

    response = await client.get("/conversations/missing-conv/results")

    assert response.status_code == 404


# ─── GET /conversations/{id}/messages ────────────────────────────────────────

async def test_get_conversation_messages_happy(client, mock_repo):
    mock_repo.get_messages = AsyncMock(
        return_value=[{"role": "user", "content": "How do people commute?"}]
    )

    response = await client.get("/conversations/conv-1/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conv-1"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"


async def test_get_conversation_messages_not_found(client, mock_repo):
    mock_repo.get_messages = AsyncMock(return_value=[])

    response = await client.get("/conversations/missing-conv/messages")

    assert response.status_code == 404

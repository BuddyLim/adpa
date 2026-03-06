from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Conversation
from app.services.query import QueryService

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    # All repo methods are async, so mock them as AsyncMock
    repo.get_conversation = AsyncMock(return_value=None)
    repo.create_conversation = AsyncMock(return_value="conv-123")
    repo.create_user_message = AsyncMock(return_value="msg-456")
    repo.get_conversation = AsyncMock(return_value=Conversation(id='abc-123'))
    repo.create_pipeline_run = AsyncMock(return_value=None)
    repo.update_conversation_title = AsyncMock(return_value=None)
    return repo


async def test_initiate_creates_new_conversation(mock_repo):
    service = QueryService(repo=mock_repo)
    user_msg = "what is 1+1?"
    _task_id, conv_id, _title = await service.initiate(user_msg, None)

    assert conv_id == "conv-123"
    mock_repo.create_conversation.assert_called_once()
    mock_repo.create_user_message.assert_called_once_with(conv_id, user_msg)
    mock_repo.create_pipeline_run.assert_called_once()

async def test_initiate_continues_coversation(mock_repo):
    service = QueryService(repo=mock_repo)
    user_msg = "what is 1+1?"

    existing_conv_id = "abc-123"
    _task_id, conv_id, _title = await service.initiate(user_msg, existing_conv_id)

    assert conv_id == existing_conv_id
    mock_repo.get_conversation.assert_called_once()
    mock_repo.create_user_message.assert_called_once_with(conv_id, user_msg)
    mock_repo.create_pipeline_run.assert_called_once()

async def test_initiate_raises_if_conversation_not_found(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=None)

    service = QueryService(repo=mock_repo)
    with pytest.raises(ValueError, match="not found"):
        await service.initiate(
            question="Some question",
            conversation_id="nonexistent-id",
        )

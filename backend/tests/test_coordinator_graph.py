import pytest

from app.agents.coordinator_graph import _format_conversation_for_prompt, _require
from app.schemas.query import ConversationMessage

pytestmark = pytest.mark.anyio


def test_format_conversation_for_prompt_with_history():
    history = [ConversationMessage(role="user", content="How do people commute?")]
    result = _format_conversation_for_prompt(history=history, prior_datasets_used=[], prior_analyses=[])
    assert "=== Conversation History ===" in result
    assert "USER: How do people commute?" in result
    assert "=== End History ===" in result


def test_require_raises_on_none():
    with pytest.raises(RuntimeError, match="intent"):
        _require(None, "intent")

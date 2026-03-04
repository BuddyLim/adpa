import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.agents.coordinator import coordinator_agent

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


async def test_coordinator_rejects_invalid_queries():
    # Test cases: unrelated query, vague query, personal info request
    with coordinator_agent.override(model=TestModel()):
        result = await coordinator_agent.run("What's the weather today?")

        assert not result.output.accepted
        assert result.output.reason  # Should explain why rejected
        assert result.output.refined_query is None

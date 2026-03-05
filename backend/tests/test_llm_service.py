import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, TextPart

pytestmark = pytest.mark.anyio

def failing_primary(_messages, _info):
    raise ModelAPIError("openai", "Simulated OpenAI outage")

def working_secondary(_messages, _info):
    return ModelResponse(parts=[TextPart("response from fallback")])

async def test_falls_back_to_secondary_on_primary_failure():
    model = FallbackModel(FunctionModel(failing_primary), FunctionModel(working_secondary))
    agent = Agent(model)

    result = await agent.run("test query")
    assert result.output == "response from fallback"

async def test_uses_primary_when_available():
    def working_primary(_messages, _info):
        return ModelResponse(parts=[TextPart("response from primary")])

    model = FallbackModel(FunctionModel(working_primary), FunctionModel(working_secondary))
    agent = Agent(model)

    result = await agent.run("test query")
    assert result.output == "response from primary"

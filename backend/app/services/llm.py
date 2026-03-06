from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.fallback import FallbackModel


from app.config import settings


def get_llm_model_with_fallback():
    """Create LLM model with fallback support.

    Returns OpenAI as primary, with Google as fallback if both keys are available.
    If only one key is available, returns that single provider.
    """
    primary_provider = OpenAIProvider(api_key=settings.openai_key)
    primary_model = OpenAIResponsesModel("chatgpt-4o-latest", provider=primary_provider)

    secondary_provider = GoogleProvider(api_key=settings.gcp_key)
    secondary_model = GoogleModel("gemini-3-flash-preview", provider=secondary_provider)

    model = FallbackModel(primary_model, secondary_model)

    return model

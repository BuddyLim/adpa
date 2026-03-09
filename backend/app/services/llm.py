from pydantic_ai import ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.fallback import FallbackModel

import openai
from app.config import settings


def get_llm_model_with_fallback():
    """Create LLM model with fallback support.

    Returns OpenAI as primary, with Google as fallback if both keys are available.
    If only one key is available, returns that single provider.
    """
    model_settings = ModelSettings(temperature=0.0)

    models = []

    if settings.openai_key:
        # ensure fallback; see https://github.com/Arjun-Vashistha/Test-Repo-2/issues/365
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_key, max_retries=0)

        primary_provider = OpenAIProvider(openai_client=openai_client)
        models.append(OpenAIResponsesModel("gpt-5-chat-latest", provider=primary_provider, settings=model_settings))

    if settings.gcp_key:
        secondary_provider = GoogleProvider(api_key=settings.gcp_key)
        models.append(GoogleModel("gemini-3-flash-preview", provider=secondary_provider, settings=model_settings))

    if not models:
        raise RuntimeError("No LLM API keys configured. Set OPENAI_KEY or GCP_KEY.")

    return models[0] if len(models) == 1 else FallbackModel(*models)

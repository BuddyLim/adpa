import json

import logfire
from pydantic_ai import Agent

from app.schemas.query import CoordinatorDecision
from app.services.llm import get_llm_model_with_fallback

coordinator_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a query gatekeeper for a policy data analytics platform.
    Get the available datasets and evaluate the relevance of the query to the datasets available
    
    Reject queries that are:
    - Completely unrelated to the data domain
    - Too vague to action (e.g. "tell me about Singapore")
    - Asking for personal, real-time, or non-statistical information
    """,
    output_type=CoordinatorDecision,
)


@coordinator_agent.tool_plain
def list_datasets() -> str:
    """Get all available datasets relevant to the query"""

    logfire.info("Coordinator tool called: list_datasets")
    with open("./app/mock_data/data.json", "r") as file:
        # Parse the JSON data into a Python dictionary
        data = json.load(file)

        return data

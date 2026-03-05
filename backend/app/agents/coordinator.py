import json
from pathlib import Path

from attr import dataclass
import logfire
from pydantic_ai import Agent, RunContext

from app.repositories.pipeline import PipelineRepository
from app.schemas.query import CoordinatorDecision
from app.services.llm import get_llm_model_with_fallback

@dataclass
class CoordinatorDeps:
    pipeline_repo: PipelineRepository

coordinator_agent = Agent(
    get_llm_model_with_fallback(),
    system_prompt="""
    You are a query gatekeeper for a policy data analytics platform.
    Get the available datasets and evaluate the relevance of the query to the datasets available

    Reject queries that are:
    - Completely unrelated to the data domain
    - Too vague to action (e.g. "tell me about Singapore")
    - Asking for personal, real-time, or non-statistical information

    If the query is accepted, enrich the user's prompt to improve the analytical understanding of the data domain
    """,
    output_type=CoordinatorDecision,
    deps_type=CoordinatorDeps
)


@coordinator_agent.tool
async def list_datasets(ctx: RunContext[CoordinatorDeps]):
    """Get all available datasets relevant to the query"""

    logfire.info("Coordinator tool called: list_datasets")
    return await ctx.deps.pipeline_repo.list_datasets() 

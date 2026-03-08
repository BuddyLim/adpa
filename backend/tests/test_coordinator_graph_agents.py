import json

import pytest
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.agents.coordinator_graph import (
    dataset_selector_agent,
    dataset_validator_agent,
    intent_agent,
    research_planner_agent,
)

pytestmark = pytest.mark.anyio
models.ALLOW_MODEL_REQUESTS = False


# ─── intent_agent ─────────────────────────────────────────────────────────────

def intent_feasible_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": True,
        "is_followup": False,
        "domain": "transport",
        "enhanced_query": "Analyse commute modes across Singapore residents.",
        "suggested_prior_datasets": [],
        "rejection_reason": None,
    }))])


def intent_infeasible_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "is_feasible": False,
        "is_followup": False,
        "domain": "unknown",
        "enhanced_query": "tell me about everything",
        "suggested_prior_datasets": [],
        "rejection_reason": "Query is too vague to map to any dataset.",
    }))])


async def test_intent_agent_feasible():
    with intent_agent.override(model=FunctionModel(intent_feasible_handler)):
        result = await intent_agent.run("How do Singaporeans commute?")
    assert result.output.is_feasible is True
    assert result.output.domain == "transport"
    assert result.output.rejection_reason is None


async def test_intent_agent_infeasible():
    with intent_agent.override(model=FunctionModel(intent_infeasible_handler)):
        result = await intent_agent.run("Tell me everything about everything.")
    assert result.output.is_feasible is False
    assert result.output.rejection_reason is not None
    assert result.output.rejection_reason != ""


# ─── dataset_selector_agent ───────────────────────────────────────────────────

def selector_selects_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "selected_datasets": [
            {
                "title": "Commute Dataset",
                "path": "commute.csv",
                "selection_reason": "Contains commute mode data.",
            }
        ],
        "cannot_answer": False,
        "reason": "",
    }))])


def selector_cannot_answer_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "selected_datasets": [],
        "cannot_answer": True,
        "reason": "No dataset covers the requested metric.",
    }))])


async def test_dataset_selector_agent_selects():
    with dataset_selector_agent.override(model=FunctionModel(selector_selects_handler)):
        result = await dataset_selector_agent.run("Commute mode by age group.")
    assert result.output.cannot_answer is False
    assert len(result.output.selected_datasets) > 0
    assert result.output.selected_datasets[0].title == "Commute Dataset"


async def test_dataset_selector_agent_cannot_answer():
    with dataset_selector_agent.override(model=FunctionModel(selector_cannot_answer_handler)):
        result = await dataset_selector_agent.run("Stock prices in 1920.")
    assert result.output.cannot_answer is True
    assert result.output.reason != ""


# ─── dataset_validator_agent ──────────────────────────────────────────────────

def validator_valid_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "valid": True,
        "confirmation_reason": "Dataset covers the required commute mode metrics.",
        "feedback": "",
    }))])


def validator_invalid_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "valid": False,
        "confirmation_reason": "",
        "feedback": "Dataset does not contain employment data required by the query.",
    }))])


async def test_dataset_validator_agent_valid():
    with dataset_validator_agent.override(model=FunctionModel(validator_valid_handler)):
        result = await dataset_validator_agent.run("Validate commute dataset for transport query.")
    assert result.output.valid is True
    assert result.output.confirmation_reason != ""


async def test_dataset_validator_agent_invalid():
    with dataset_validator_agent.override(model=FunctionModel(validator_invalid_handler)):
        result = await dataset_validator_agent.run("Validate housing dataset for employment query.")
    assert result.output.valid is False
    assert result.output.feedback != ""


# ─── research_planner_agent ───────────────────────────────────────────────────

def planner_happy_handler(_messages, _info):
    return ModelResponse(parts=[TextPart(json.dumps({
        "analysis_type": "comparison",
        "sub_questions": [
            "Which transport mode is most used?",
            "How does usage vary by age group?",
        ],
        "key_metrics": ["count", "transport_mode"],
        "extraction_hints": {"Commute Dataset": "Select transport_mode and count columns."},
        "suggested_chart_types": ["bar", "pie"],
    }))])


def planner_bad_handler(_messages, _info):
    return ModelResponse(parts=[TextPart("this is not valid json {")])


async def test_research_planner_agent_happy():
    with research_planner_agent.override(model=FunctionModel(planner_happy_handler)):
        result = await research_planner_agent.run("Plan analysis for commute query.")
    assert result.output.analysis_type == "comparison"
    assert len(result.output.sub_questions) >= 2
    assert "bar" in result.output.suggested_chart_types


async def test_research_planner_agent_bad_output():
    with pytest.raises(Exception):
        with research_planner_agent.override(model=FunctionModel(planner_bad_handler)):
            await research_planner_agent.run("Plan analysis for commute query.")

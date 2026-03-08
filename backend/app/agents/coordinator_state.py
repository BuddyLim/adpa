import asyncio
from dataclasses import dataclass, field

from app.repositories.pipeline import PipelineRepository
from app.schemas.query import (
    AnalysisResult,
    ConversationMessage,
    DatasetInfo,
    DatasetSelectionOutput,
    ExtractionResult,
    IntentAnalysis,
    NormalizationResult,
    PriorAnalysis,
    ResearchPlan,
)


@dataclass
class CoordinatorState:
    raw_query: str
    conversation_id: str
    pipeline_run_id: str
    # Loaded by LoadContextNode
    available_datasets: list[DatasetInfo] = field(default_factory=list)
    conversation_history: list[ConversationMessage] = field(default_factory=list)
    prior_datasets_used: list[str] = field(default_factory=list)
    prior_analyses: list[PriorAnalysis] = field(default_factory=list)
    # Coordinator nodes
    intent: IntentAnalysis | None = None
    dataset_selection: DatasetSelectionOutput | None = None
    validation_feedback: str | None = None
    selection_iterations: int = 0
    dataset_ids: dict[str, str] = field(default_factory=dict)
    # Planning node
    research_plan: ResearchPlan | None = None
    # Pipeline nodes
    extraction_results: list[ExtractionResult] = field(default_factory=list)
    normalization_result: NormalizationResult | None = None
    analysis_result: AnalysisResult | None = None
    analysis_iterations: int = 0
    analysis_feedback: str | None = None
    # Root-cause routing (set by ValidateAnalysisNode when routing upstream)
    extraction_feedback: str | None = None  # consumed by PlanResearchNode / SelectDatasetsNode
    pipeline_iterations: int = 0            # counts backward re-entries past AnalyzeNode
    # Step order counter for DB persistence
    step_order: int = 0
    # Queue for real-time SSE event streaming; None sentinel signals completion
    sse_queue: asyncio.Queue = field(default_factory=asyncio.Queue)


@dataclass
class CoordinatorGraphDeps:
    pipeline_repo: PipelineRepository
    pipeline_run_id: str

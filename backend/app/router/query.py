from datetime import datetime

import logfire
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.repositories.pipeline import PipelineRepository, get_pipeline_repo
from app.schemas.query import AnalysisResult, ChartConfig
from app.services.query import QueryService, get_query_service


class DatasetSummary(BaseModel):
    id: str
    title: str


class StepSummary(BaseModel):
    message: str
    step_type: str | None = None


class ExtractionSummary(BaseModel):
    datasets: list[dict]  # [{title, row_count}]
    total_rows: int


class NormalizationSummary(BaseModel):
    unified_rows: int
    columns: list[str]


class PipelineRunResult(BaseModel):
    pipeline_run_id: str
    status: str
    enhanced_query: str | None
    created_at: datetime
    completed_at: datetime | None
    datasets: list[DatasetSummary]
    steps: list[StepSummary]
    extraction: ExtractionSummary | None
    normalization: NormalizationSummary | None
    analysis: AnalysisResult | None


class ConversationResultsResponse(BaseModel):
    conversation_id: str
    results: list[PipelineRunResult]

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    conversation_id: str | None = None


@router.post("/query")
async def query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    service: QueryService = Depends(get_query_service),
):
    try:
        task_id, conversation_id, title = await service.initiate(
            request.question, request.conversation_id
        )
        background_tasks.add_task(service.get_producer())
        logfire.info("query accepted", task_id=task_id, conversation_id=conversation_id)
        return {"task_id": task_id, "conversation_id": conversation_id, "title": title}
    except ValueError as err:
        logfire.warn("conversation not found", conversation_id=request.conversation_id)
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        logfire.error("query initiation failed", error=str(err), exc_info=True)
        raise HTTPException(status_code=500) from err


@router.get("/query/{id}/stream")
async def get_query_stream(
    id: str,
    service: QueryService = Depends(get_query_service),
):
    queue = service.get_stream(id)
    if not queue:
        logfire.warn("stream not found", task_id=id)
        raise HTTPException(status_code=404)

    async def consume():
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(consume(), media_type="text/event-stream")


@router.get("/conversations/{conversation_id}/results", response_model=ConversationResultsResponse)
async def get_conversation_results(
    conversation_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
):
    """Return all completed pipeline runs and their analysis results for a conversation."""
    runs = await repo.get_conversation_results(conversation_id)
    if not runs:
        raise HTTPException(status_code=404, detail="Conversation not found or has no pipeline runs")

    results: list[PipelineRunResult] = []
    for run in runs:
        analysis = None
        if run.analysis_result:
            ar = run.analysis_result
            analysis = AnalysisResult(
                summary=ar.summary,
                key_findings=ar.key_findings,
                chart_configs=[ChartConfig.model_validate(c) for c in ar.chart_configs],
            )
        extraction = None
        if run.extraction_results:
            dataset_rows = [
                {"title": er.source_dataset, "row_count": len(er.rows)}
                for er in run.extraction_results
            ]
            extraction = ExtractionSummary(
                datasets=dataset_rows,
                total_rows=sum(d["row_count"] for d in dataset_rows),
            )

        normalization = None
        if run.normalization_result:
            nr = run.normalization_result
            normalization = NormalizationSummary(
                unified_rows=len(nr.unified_rows),
                columns=nr.columns,
            )

        results.append(PipelineRunResult(
            pipeline_run_id=run.id,
            status=run.status,
            enhanced_query=run.enhanced_query,
            created_at=run.created_at,
            completed_at=run.completed_at,
            datasets=[DatasetSummary(id=ds.id, title=ds.title) for ds in run.datasets],
            steps=[StepSummary(message=s.message, step_type=s.step_type) for s in sorted(run.steps, key=lambda s: s.step_order)],
            extraction=extraction,
            normalization=normalization,
            analysis=analysis,
        ))

    return ConversationResultsResponse(conversation_id=conversation_id, results=results)


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    repo: PipelineRepository = Depends(get_pipeline_repo),
):
    """Return all messages (user + assistant) for a conversation."""
    messages = await repo.get_messages(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or has no messages")
    return {"conversation_id": conversation_id, "messages": messages}

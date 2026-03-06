from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from typing import AsyncGenerator

import logfire
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import AsyncSessionLocal
from app.db.models import AnalysisResultRecord, Conversation, Dataset, ExtractionResultRecord, Message, NormalizationResultRecord, PipelineRun, PipelineStep
from app.schemas.query import AnalysisResult, CoordinatorDecision, ExtractionResult, NormalizationResult


class PipelineRepository:
    """
    Each method opens and closes its own session — no session is held open
    across agent calls or yields, preventing connection leaks on long-running work.
    """

    @asynccontextmanager
    async def _db_span(self, span_name: str, **attrs) -> AsyncGenerator[AsyncSession, None]:
        with logfire.span(span_name, **attrs):
            try:
                async with AsyncSessionLocal() as db:
                    yield db
            except Exception as err:
                logfire.error(f"failed: {span_name}", error=str(err), exc_info=True, **attrs)
                raise

    async def create_conversation(self) -> str:
        async with self._db_span("db: create conversation") as db:
            conversation = Conversation()
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            logfire.info("conversation created", conversation_id=conversation.id)
            return conversation.id

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        async with self._db_span("db: get conversation", conversation_id=conversation_id) as db:
            conversation = await db.get(Conversation, conversation_id)
            if not conversation:
                logfire.warn("conversation not found", conversation_id=conversation_id)
            return conversation

    async def create_user_message(self, conversation_id: str, content: str) -> str:
        async with self._db_span("db: create user message", conversation_id=conversation_id) as db:
            message = Message(conversation_id=conversation_id, role="user", content=content)
            db.add(message)
            await db.commit()
            await db.refresh(message)
            logfire.info("user message created", message_id=message.id)
            return message.id

    async def create_pipeline_run(self, run_id: str, message_id: str) -> None:
        async with self._db_span("db: create pipeline run", run_id=run_id, message_id=message_id) as db:
            db.add(PipelineRun(id=run_id, message_id=message_id))
            await db.commit()
            logfire.info("pipeline run created", run_id=run_id)

    async def mark_running(self, run_id: str) -> None:
        async with self._db_span("db: mark pipeline running", run_id=run_id) as db:
            run = await db.get(PipelineRun, run_id)
            if run is None:
                raise ValueError(f"Pipeline run {run_id} not found")
            run.status = "running"
            await db.commit()

    async def add_step(self, run_id: str, order: int, message: str) -> None:
        async with self._db_span("db: add pipeline step", run_id=run_id, step_order=order) as db:
            db.add(PipelineStep(pipeline_run_id=run_id, step_order=order, message=message))
            await db.commit()

    async def complete_run(self, run_id: str, decision: CoordinatorDecision) -> None:
        async with self._db_span("db: complete pipeline run", run_id=run_id, accepted=decision.accepted) as db:
            result = await db.execute(
                select(PipelineRun).options(selectinload(PipelineRun.datasets)).where(PipelineRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                raise ValueError(f"Pipeline run {run_id} not found")
            run.accepted = decision.accepted
            run.reason = decision.reason
            run.enhanced_query = decision.enhanced_query
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

            if decision.dataset_selected:
                for ds in decision.dataset_selected:
                    result = await db.execute(select(Dataset).where(Dataset.file_path == ds.path))
                    dataset = result.scalar_one_or_none()
                    if not dataset:
                        dataset = Dataset(title=ds.title, file_path=ds.path)
                        db.add(dataset)
                        await db.flush()
                        logfire.info("dataset created", title=ds.title, file_path=ds.path)
                    run.datasets.append(dataset)

            await db.commit()
            logfire.info("pipeline run completed", run_id=run_id, accepted=decision.accepted)

    async def add_assistant_message(self, conversation_id: str, content: str) -> None:
        async with self._db_span("db: add assistant message", conversation_id=conversation_id) as db:
            db.add(Message(conversation_id=conversation_id, role="assistant", content=content))
            await db.commit()
            logfire.info("assistant message added", conversation_id=conversation_id)

    async def save_extraction_results(self, run_id: str, results: list[ExtractionResult]) -> None:
        async with self._db_span("db: save extraction results", run_id=run_id, n_results=len(results)) as db:
            for r in results:
                db.add(ExtractionResultRecord(
                    pipeline_run_id=run_id,
                    source_dataset=r.source_dataset,
                    summary=r.summary,
                    rows=r.rows,
                    join_keys=r.join_keys,
                    sql_query=r.sql_query,
                ))
            await db.commit()
            logfire.info("extraction results saved", run_id=run_id, n_results=len(results))

    async def save_normalization_result(self, run_id: str, result: NormalizationResult) -> None:
        async with self._db_span("db: save normalization result", run_id=run_id) as db:
            db.add(NormalizationResultRecord(
                pipeline_run_id=run_id,
                notes=result.notes,
                unified_rows=result.unified_rows,
                columns=result.columns,
            ))
            await db.commit()
            logfire.info("normalization result saved", run_id=run_id)

    async def save_analysis_result(self, run_id: str, result: AnalysisResult) -> None:
        async with self._db_span("db: save analysis result", run_id=run_id) as db:
            db.add(AnalysisResultRecord(
                pipeline_run_id=run_id,
                summary=result.summary,
                key_findings=result.key_findings,
                chart_configs=[c.model_dump() for c in result.chart_configs],
            ))
            await db.commit()
            logfire.info("analysis result saved", run_id=run_id)

    async def list_datasets(self):
        async with self._db_span("db: getting datasets") as db:
            stmt = select(Dataset)
            result = await db.execute(stmt)
            datasets = result.scalars().all()
            return json.dumps([
                {"title": d.title, "description": d.summary, "path": d.file_path}
                for d in datasets
            ])

    async def get_messages(self, conversation_id: str) -> list[dict]:
        async with self._db_span("db: get messages", conversation_id=conversation_id) as db:
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            messages = result.scalars().all()
            return [{"role": m.role, "content": m.content} for m in messages]


def get_pipeline_repo() -> PipelineRepository:
    return PipelineRepository()

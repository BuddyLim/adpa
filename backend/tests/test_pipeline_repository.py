import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.db.database import Base
from app.db.models import Dataset, PipelineRun
from app.repositories.pipeline import PipelineRepository
from app.schemas.query import CoordinatorDataset, CoordinatorDecision

pytestmark = pytest.mark.anyio


@pytest.fixture
async def db_setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    with patch("app.repositories.pipeline.AsyncSessionLocal", TestSession):
        yield PipelineRepository(), TestSession

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_full_pipeline_lifecycle_accepted(db_setup):
    """Full happy path: conversation → message → run → step → complete (accepted) → assistant reply."""
    repo, TestSession = db_setup
    run_id = str(uuid.uuid4())

    conv_id = await repo.create_conversation()
    assert conv_id

    msg_id = await repo.create_user_message(conv_id, "How do people commute?")
    assert msg_id

    await repo.create_pipeline_run(run_id, msg_id)
    await repo.mark_running(run_id)
    await repo.add_step(run_id, 1, "Searching datasets...")

    decision = CoordinatorDecision(
        accepted=True,
        reason="Found relevant dataset",
        enhanced_query="commute mode by age group",
        dataset_selected=[CoordinatorDataset(title="Commuting Data", path="data/commute.csv")],
    )
    await repo.complete_run(run_id, decision)
    await repo.add_assistant_message(conv_id, "Here are the results.")

    async with TestSession() as db:
        result = await db.execute(
            select(PipelineRun)
            .options(selectinload(PipelineRun.datasets))
            .where(PipelineRun.id == run_id)
        )
        run = result.scalar_one()

    assert run.status == "completed"
    assert run.accepted is True
    assert run.reason == "Found relevant dataset"
    assert run.enhanced_query == "commute mode by age group"
    assert run.completed_at is not None
    assert len(run.datasets) == 1
    assert run.datasets[0].file_path == "data/commute.csv"
    assert run.datasets[0].title == "Commuting Data"


async def test_pipeline_run_rejection(db_setup):
    """Rejection path: complete_run with accepted=False creates no Dataset rows."""
    repo, TestSession = db_setup
    run_id = str(uuid.uuid4())

    conv_id = await repo.create_conversation()
    msg_id = await repo.create_user_message(conv_id, "What is the weather today?")
    await repo.create_pipeline_run(run_id, msg_id)

    decision = CoordinatorDecision(
        accepted=False,
        reason="No relevant dataset found",
        enhanced_query="current weather data",
        dataset_selected=None,
    )
    await repo.complete_run(run_id, decision)

    async with TestSession() as db:
        result = await db.execute(
            select(PipelineRun)
            .options(selectinload(PipelineRun.datasets))
            .where(PipelineRun.id == run_id)
        )
        run = result.scalar_one()
        all_datasets = (await db.execute(select(Dataset))).scalars().all()

    assert run.status == "completed"
    assert run.accepted is False
    assert run.reason == "No relevant dataset found"
    assert run.datasets == []
    assert all_datasets == []

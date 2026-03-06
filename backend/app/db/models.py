import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    pipeline_run: Mapped["PipelineRun | None"] = relationship(
        back_populates="message", uselist=False
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # The user message that triggered this run
    message_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    enhanced_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    message: Mapped["Message"] = relationship(back_populates="pipeline_run")
    steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="pipeline_run", order_by="PipelineStep.step_order"
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        secondary="pipeline_run_datasets", back_populates="pipeline_runs"
    )
    extraction_results: Mapped[list["ExtractionResultRecord"]] = relationship(
        back_populates="pipeline_run", order_by="ExtractionResultRecord.created_at"
    )
    normalization_result: Mapped["NormalizationResultRecord | None"] = relationship(
        back_populates="pipeline_run", uselist=False
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="steps")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        secondary="pipeline_run_datasets", back_populates="datasets"
    )


class PipelineRunDataset(Base):
    __tablename__ = "pipeline_run_datasets"

    pipeline_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(
        String, ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True
    )


class ExtractionResultRecord(Base):
    __tablename__ = "extraction_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pipeline_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_dataset: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rows: Mapped[list] = mapped_column(JSON, nullable=False)
    join_keys: Mapped[list] = mapped_column(JSON, nullable=False)
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="extraction_results")


class NormalizationResultRecord(Base):
    __tablename__ = "normalization_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pipeline_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    unified_rows: Mapped[list] = mapped_column(JSON, nullable=False)
    columns: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="normalization_result")

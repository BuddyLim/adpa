"""add extraction and normalization result tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extraction_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("pipeline_run_id", sa.String(), nullable=False),
        sa.Column("source_dataset", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("join_keys", sa.JSON(), nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "normalization_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("pipeline_run_id", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("unified_rows", sa.JSON(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_run_id"),
    )


def downgrade() -> None:
    op.drop_table("normalization_results")
    op.drop_table("extraction_results")

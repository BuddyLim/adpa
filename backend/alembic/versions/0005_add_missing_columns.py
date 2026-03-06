"""add missing columns to pipeline_runs and pipeline_steps

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_runs") as batch_op:
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("error_stage", sa.String(length=50), nullable=True))

    with op.batch_alter_table("pipeline_steps") as batch_op:
        batch_op.add_column(sa.Column("step_type", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_steps") as batch_op:
        batch_op.drop_column("step_type")

    with op.batch_alter_table("pipeline_runs") as batch_op:
        batch_op.drop_column("error_stage")
        batch_op.drop_column("error_message")

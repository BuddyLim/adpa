"""add historical conversations

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-06 21:20:15.191182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clean up any orphaned temp tables from a previously interrupted batch operation
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_extraction_results"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_pipeline_runs"))

    with op.batch_alter_table('extraction_results') as batch_op:
        batch_op.add_column(sa.Column('dataset_id', sa.String(), nullable=True))
        batch_op.create_index('ix_extraction_results_dataset_id', ['dataset_id'], unique=False)
        batch_op.create_foreign_key('fk_extraction_results_dataset_id', 'datasets', ['dataset_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('pipeline_runs') as batch_op:
        batch_op.add_column(sa.Column('conversation_id', sa.String(), nullable=True))
        batch_op.create_index('ix_pipeline_runs_conversation_id', ['conversation_id'], unique=False)
        batch_op.create_foreign_key('fk_pipeline_runs_conversation_id', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    with op.batch_alter_table('pipeline_runs') as batch_op:
        batch_op.drop_constraint('fk_pipeline_runs_conversation_id', type_='foreignkey')
        batch_op.drop_index('ix_pipeline_runs_conversation_id')
        batch_op.drop_column('conversation_id')

    with op.batch_alter_table('extraction_results') as batch_op:
        batch_op.drop_constraint('fk_extraction_results_dataset_id', type_='foreignkey')
        batch_op.drop_index('ix_extraction_results_dataset_id')
        batch_op.drop_column('dataset_id')

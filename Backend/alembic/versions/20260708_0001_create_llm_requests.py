"""Create llm_requests analytics table

Revision ID: 20260708_0001
Revises:
Create Date: 2026-07-08

Persists one row per LLM API call with real token/cost data (see
src/utils/llm_instrumentation.py). Mirrors the CREATE TABLE IF NOT EXISTS in
src/database/init_db.py, which remains in place as a defensive fallback for
already-running deployments that pick up code changes without an explicit
`alembic upgrade` step; this migration is the source of truth for fresh
setups and any environment that runs migrations explicitly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260708_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("chat_id", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("system_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("history_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rag_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_llm_requests_user_created", "llm_requests", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_llm_requests_chat_created", "llm_requests", ["chat_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_requests_chat_created", table_name="llm_requests")
    op.drop_index("ix_llm_requests_user_created", table_name="llm_requests")
    op.drop_table("llm_requests")

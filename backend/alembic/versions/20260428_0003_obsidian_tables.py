"""obsidian — app_settings + obsidian_conflicts + trades.last_obsidian_sync_at

Revision ID: 0003_obsidian_tables
Revises: 0002_seed_defaults
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_obsidian_tables"
down_revision: str | None = "0002_seed_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- app_settings -------------------------------------------------------
    op.create_table(
        "app_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "obsidian_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "obsidian_vault_path",
            sa.String(),
            nullable=False,
            server_default="/vault",
        ),
        sa.Column(
            "obsidian_sync_mode",
            sa.String(),
            nullable=False,
            server_default="export_only",
        ),
        sa.Column(
            "obsidian_template_set",
            sa.String(),
            nullable=False,
            server_default="complete",
        ),
        sa.Column("obsidian_last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("obsidian_last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Seed the single row.
    op.execute("INSERT INTO app_settings DEFAULT VALUES")

    # --- obsidian_conflicts -------------------------------------------------
    op.create_table(
        "obsidian_conflicts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("trade_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("db_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("db_text", sa.Text(), nullable=True),
        sa.Column("file_text", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_obsidian_conflicts_unresolved",
        "obsidian_conflicts",
        ["resolved_at"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    # --- trades.last_obsidian_sync_at --------------------------------------
    op.add_column(
        "trades",
        sa.Column("last_obsidian_sync_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trades", "last_obsidian_sync_at")
    op.drop_index("ix_obsidian_conflicts_unresolved", table_name="obsidian_conflicts")
    op.drop_table("obsidian_conflicts")
    op.drop_table("app_settings")

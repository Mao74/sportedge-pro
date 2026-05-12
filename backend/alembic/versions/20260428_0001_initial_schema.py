"""initial schema — users, strategies, trades, tags, snapshots, reflections, whatif

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-28

Sets up the full data model from docs/architecture.md. Idempotent on the
extensions; pure CREATE/DROP for tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum types are created/dropped explicitly via .create() / .drop() — the
# column definitions reference them with create_type=False so create_table
# doesn't try to recreate them implicitly.
STRATEGY_KIND = postgresql.ENUM("builtin", "custom", name="strategy_kind")
PNL_MODE = postgresql.ENUM("AUTO", "MANUAL", "CASHOUT_ODDS", name="pnl_mode")
TRADE_STATUS = postgresql.ENUM("OPEN", "CLOSED", "VOID", name="trade_status")

STRATEGY_KIND_COL = postgresql.ENUM(
    "builtin", "custom", name="strategy_kind", create_type=False
)
PNL_MODE_COL = postgresql.ENUM(
    "AUTO", "MANUAL", "CASHOUT_ODDS", name="pnl_mode", create_type=False
)
TRADE_STATUS_COL = postgresql.ENUM(
    "OPEN", "CLOSED", "VOID", name="trade_status", create_type=False
)


def upgrade() -> None:
    # pgcrypto is needed for gen_random_uuid().
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- strategies ---
    STRATEGY_KIND.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "strategies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("kind", STRATEGY_KIND_COL, nullable=False),
        sa.Column("template_key", sa.String(), nullable=True),
        sa.Column("sport", sa.String(), nullable=False, server_default="football"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color_hex", sa.String(length=9), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "field_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_strategies_slug"),
        sa.CheckConstraint(
            "(kind = 'builtin' AND template_key IS NOT NULL) "
            "OR (kind = 'custom' AND template_key IS NULL)",
            name="ck_strategies_strategies_template_key_kind",
        ),
    )
    op.create_index(
        "ix_strategies_kind_is_active", "strategies", ["kind", "is_active"], unique=False
    )

    # --- trades ---
    PNL_MODE.create(op.get_bind(), checkfirst=True)
    TRADE_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport", sa.String(), nullable=False, server_default="football"),
        sa.Column("home_team", sa.String(), nullable=False),
        sa.Column("away_team", sa.String(), nullable=False),
        sa.Column("league", sa.String(), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ht_score_home", sa.Integer(), nullable=True),
        sa.Column("ht_score_away", sa.Integer(), nullable=True),
        sa.Column("ft_score_home", sa.Integer(), nullable=True),
        sa.Column("ft_score_away", sa.Integer(), nullable=True),
        sa.Column("stake_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("avg_odds", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "commission_pct", sa.Numeric(4, 2), nullable=False, server_default="5.00"
        ),
        sa.Column("pnl_mode", PNL_MODE_COL, nullable=False),
        sa.Column("cashout_odds", sa.Numeric(6, 2), nullable=True),
        sa.Column("manual_pnl_eur", sa.Numeric(10, 2), nullable=True),
        sa.Column("computed_pnl_eur", sa.Numeric(10, 2), nullable=False),
        sa.Column("outcome_label", sa.String(), nullable=True),
        sa.Column("status", TRADE_STATUS_COL, nullable=False, server_default="OPEN"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "strategy_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes_md", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["strategies.id"],
            name="fk_trades_strategy_id_strategies",
            ondelete="RESTRICT",
        ),
    )
    # Indices — declared via raw SQL for the non-trivial ones (DESC, partial, GIN expression).
    op.execute("CREATE INDEX ix_trades_kickoff_at ON trades (kickoff_at DESC)")
    op.execute(
        "CREATE INDEX ix_trades_strategy_kickoff ON trades (strategy_id, kickoff_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_trades_status_open ON trades (status) WHERE status = 'OPEN'"
    )
    op.execute(
        "CREATE INDEX ix_trades_strategy_data_gin ON trades USING GIN (strategy_data)"
    )
    op.execute(
        "CREATE INDEX ix_trades_search_gin ON trades USING GIN ("
        "to_tsvector('simple', "
        "home_team || ' ' || away_team || ' ' || coalesce(notes_md, ''))"
        ")"
    )

    # --- tags + trade_tags ---
    op.create_table(
        "tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color_hex", sa.String(length=9), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    op.create_table(
        "trade_tags",
        sa.Column("trade_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            ["trades.id"],
            name="fk_trade_tags_trade_id_trades",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_trade_tags_tag_id_tags",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("trade_id", "tag_id", name="pk_trade_tags"),
    )

    # --- bankroll_snapshots ---
    op.create_table(
        "bankroll_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("balance_eur", sa.Numeric(12, 2), nullable=False),
        sa.Column("deposit_eur", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("withdrawal_eur", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_bankroll_snapshots_taken_at ON bankroll_snapshots (taken_at DESC)"
    )

    # --- daily_reflections ---
    op.create_table(
        "daily_reflections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("reflection_md", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("date", name="uq_daily_reflections_date"),
    )

    # --- whatif_scratch ---
    op.create_table(
        "whatif_scratch",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "inputs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "outputs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("whatif_scratch")
    op.drop_table("daily_reflections")
    op.drop_index("ix_bankroll_snapshots_taken_at", table_name="bankroll_snapshots")
    op.drop_table("bankroll_snapshots")
    op.drop_table("trade_tags")
    op.drop_table("tags")
    op.drop_index("ix_trades_search_gin", table_name="trades")
    op.drop_index("ix_trades_strategy_data_gin", table_name="trades")
    op.drop_index("ix_trades_status_open", table_name="trades")
    op.drop_index("ix_trades_strategy_kickoff", table_name="trades")
    op.drop_index("ix_trades_kickoff_at", table_name="trades")
    op.drop_table("trades")
    TRADE_STATUS.drop(op.get_bind(), checkfirst=True)
    PNL_MODE.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_strategies_kind_is_active", table_name="strategies")
    op.drop_table("strategies")
    STRATEGY_KIND.drop(op.get_bind(), checkfirst=True)
    op.drop_table("users")
    # Note: we leave the pgcrypto extension in place — other tooling may rely on it.

"""multi_account — per-account bankroll + venue prefs migration

Revision ID: 0007_multi_account
Revises: 0006_market_type
Create Date: 2026-05-12

Introduces a per-trading-account model so a single user can track separate
bankrolls on different venues (Betfair Exchange + Betflag classic, etc).

Schema changes:

- New table ``accounts`` (name unique among non-archived rows, opening
  balance, market_type, commission_pct, opened_at, is_active, archived_at).
- ``trades.account_id`` FK accounts.id, NOT NULL, ON DELETE RESTRICT.
- ``bankroll_snapshots.account_id`` FK accounts.id, NOT NULL, ON DELETE
  RESTRICT.
- ``app_settings.default_account_id`` FK accounts.id, nullable, ON DELETE
  SET NULL (the account pre-selected on the new-trade form).
- Drop legacy single-venue prefs from ``app_settings``:
  ``betting_exchange``, ``default_commission_pct``, ``default_market_type``.
  These moved to the per-account record. We can drop them cleanly because
  the columns were introduced in this same deploy and nobody has booked
  trades against them yet.

Seed:

- Two starter accounts ``Betfair`` (exchange, 5% commission) and ``Betflag``
  (classic, 0% commission), each with opening_balance 1000.00 (placeholder
  — the user edits via Settings → Accounts).
- ``app_settings.default_account_id`` points at the Betfair seed.

Idempotent: both ``upgrade`` and ``downgrade`` implemented. The downgrade
ASSUMES no trades or bankroll_snapshots exist (the same precondition the
upgrade relies on); if you've already booked rows against account_id, you
need to detach them manually before rolling back.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_multi_account"
down_revision: str | None = "0006_market_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MARKET_TYPE_COL = postgresql.ENUM(
    "exchange", "classic", name="market_type", create_type=False
)


def upgrade() -> None:
    # 1. accounts table
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "venue",
            sa.String(length=32),
            nullable=False,
            server_default="betfair",
        ),
        sa.Column(
            "market_type",
            MARKET_TYPE_COL,
            nullable=False,
            server_default="exchange",
        ),
        sa.Column(
            "commission_pct",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="5.00",
        ),
        sa.Column(
            "opening_balance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "opened_at",
            sa.Date,
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "archived_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_accounts_name_unique",
        "accounts",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    # 2. Seed two starter accounts.
    accounts_table = sa.table(
        "accounts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("venue", sa.String),
        sa.column("market_type", sa.Enum("exchange", "classic", name="market_type")),
        sa.column("commission_pct", sa.Numeric),
        sa.column("opening_balance", sa.Numeric),
    )
    op.bulk_insert(
        accounts_table,
        [
            {
                "name": "Betfair",
                "venue": "betfair",
                "market_type": "exchange",
                "commission_pct": "5.00",
                "opening_balance": "1000.00",
            },
            {
                "name": "Betflag",
                "venue": "betflag",
                "market_type": "classic",
                "commission_pct": "0.00",
                "opening_balance": "1000.00",
            },
        ],
    )

    # 3. trades.account_id (NOT NULL — DB is clean at this point so no
    #    backfill is needed; if you ever rerun this on a DB with existing
    #    trades you'd need to add the column nullable, backfill, then SET
    #    NOT NULL).
    op.add_column(
        "trades",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index("ix_trades_account_id", "trades", ["account_id"])

    # 4. bankroll_snapshots.account_id (idem)
    op.add_column(
        "bankroll_snapshots",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_bankroll_snapshots_account_taken",
        "bankroll_snapshots",
        ["account_id", sa.text("taken_at DESC")],
    )

    # 5. app_settings: drop legacy single-venue prefs, add default_account_id
    op.drop_column("app_settings", "default_market_type")
    op.drop_column("app_settings", "default_commission_pct")
    op.drop_column("app_settings", "betting_exchange")
    op.add_column(
        "app_settings",
        sa.Column(
            "default_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 6. Point default_account_id at the Betfair seed (single-row table).
    op.execute(
        """
        UPDATE app_settings
        SET default_account_id = (
            SELECT id FROM accounts WHERE name = 'Betfair' LIMIT 1
        )
        """
    )


def downgrade() -> None:
    # 1. app_settings: drop default_account_id, restore legacy columns
    op.drop_column("app_settings", "default_account_id")
    op.add_column(
        "app_settings",
        sa.Column(
            "betting_exchange",
            sa.String(length=32),
            nullable=False,
            server_default="betfair",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "default_commission_pct",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="4.50",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "default_market_type",
            MARKET_TYPE_COL,
            nullable=False,
            server_default="exchange",
        ),
    )

    # 2. bankroll_snapshots.account_id off (DB must be empty for this to
    #    succeed — see migration docstring).
    op.drop_index(
        "ix_bankroll_snapshots_account_taken", table_name="bankroll_snapshots"
    )
    op.drop_column("bankroll_snapshots", "account_id")

    # 3. trades.account_id off
    op.drop_index("ix_trades_account_id", table_name="trades")
    op.drop_column("trades", "account_id")

    # 4. accounts table
    op.drop_index("ix_accounts_name_unique", table_name="accounts")
    op.drop_table("accounts")

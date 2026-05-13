"""Trading account CRUD service.

- ``list_accounts``: optionally includes archived rows.
- ``create_account``: enforces unique name among non-archived rows (also
  guaranteed by ``ix_accounts_name_unique`` partial index in DB).
- ``update_account``: patch any subset of editable fields.
- ``archive_account`` / ``unarchive_account``: soft delete via
  ``archived_at`` + ``is_active`` flags.
- ``delete_account``: hard delete; refuses with HTTP 409-equivalent error
  if the account has any trade or snapshot still pointing at it (the DB
  FK is ``ON DELETE RESTRICT``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, BankrollSnapshot, Trade
from app.schemas.account import AccountCreate, AccountUpdate


class AccountInUseError(RuntimeError):
    """Raised when a hard-delete is attempted on an account with trades or
    snapshots. The router maps this to HTTP 409."""

    def __init__(self, n_trades: int, n_snapshots: int) -> None:
        super().__init__(
            f"account in use ({n_trades} trades, {n_snapshots} snapshots)"
        )
        self.n_trades = n_trades
        self.n_snapshots = n_snapshots


class AccountNameTakenError(RuntimeError):
    """Unique-violation on (name) among non-archived rows."""


async def list_accounts(
    db: AsyncSession, *, include_archived: bool = False
) -> list[Account]:
    q = select(Account).order_by(Account.created_at.asc())
    if not include_archived:
        q = q.where(Account.archived_at.is_(None))
    res = await db.execute(q)
    return list(res.scalars())


async def get_account(db: AsyncSession, account_id: uuid.UUID) -> Account | None:
    res = await db.execute(select(Account).where(Account.id == account_id))
    return res.scalar_one_or_none()


async def get_account_by_name(db: AsyncSession, name: str) -> Account | None:
    """Used by CSV importer to resolve `account_name` strings."""
    res = await db.execute(
        select(Account)
        .where(func.lower(Account.name) == name.lower())
        .where(Account.archived_at.is_(None))
        .limit(1)
    )
    return res.scalar_one_or_none()


async def create_account(db: AsyncSession, payload: AccountCreate) -> Account:
    account = Account(
        name=payload.name,
        venue=payload.venue,
        market_type=payload.market_type,
        commission_pct=payload.commission_pct,
        opening_balance=payload.opening_balance,
    )
    if payload.opened_at is not None:
        account.opened_at = payload.opened_at
    db.add(account)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise AccountNameTakenError(str(exc)) from exc
    return account


async def update_account(
    db: AsyncSession, account: Account, patch: AccountUpdate
) -> Account:
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(account, field, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise AccountNameTakenError(str(exc)) from exc
    return account


async def archive_account(db: AsyncSession, account: Account) -> Account:
    account.is_active = False
    account.archived_at = datetime.now(UTC)
    await db.flush()
    return account


async def unarchive_account(db: AsyncSession, account: Account) -> Account:
    account.is_active = True
    account.archived_at = None
    await db.flush()
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    """Hard delete. Raises AccountInUseError if any FK references remain."""
    trades_res = await db.execute(
        select(func.count(Trade.id)).where(Trade.account_id == account.id)
    )
    snaps_res = await db.execute(
        select(func.count(BankrollSnapshot.id)).where(
            BankrollSnapshot.account_id == account.id
        )
    )
    n_trades = int(trades_res.scalar_one())
    n_snaps = int(snaps_res.scalar_one())
    if n_trades or n_snaps:
        raise AccountInUseError(n_trades, n_snaps)
    await db.delete(account)
    await db.flush()


async def opening_balance_of(db: AsyncSession, account_id: uuid.UUID) -> Decimal:
    res = await db.execute(
        select(Account.opening_balance).where(Account.id == account_id)
    )
    val = res.scalar_one_or_none()
    return Decimal(str(val)) if val is not None else Decimal("0")

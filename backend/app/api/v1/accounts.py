"""Trading accounts CRUD API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.account import Account as AccountOut
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.account_service import (
    AccountInUseError,
    AccountNameTakenError,
    archive_account,
    create_account,
    delete_account,
    get_account,
    list_accounts,
    unarchive_account,
    update_account,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_endpoint(
    _user: CurrentUser,
    db: DbSession,
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountOut]:
    rows = await list_accounts(db, include_archived=include_archived)
    return [AccountOut.model_validate(r) for r in rows]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: AccountCreate, _user: CurrentUser, db: DbSession
) -> AccountOut:
    try:
        acc = await create_account(db, payload)
    except AccountNameTakenError:
        raise HTTPException(
            status_code=409, detail=f"account name '{payload.name}' already in use"
        )
    await db.commit()
    await db.refresh(acc)
    return AccountOut.model_validate(acc)


@router.get("/{account_id}", response_model=AccountOut)
async def get_endpoint(
    account_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> AccountOut:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return AccountOut.model_validate(acc)


@router.patch("/{account_id}", response_model=AccountOut)
async def patch_endpoint(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    _user: CurrentUser,
    db: DbSession,
) -> AccountOut:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        acc = await update_account(db, acc, payload)
    except AccountNameTakenError:
        raise HTTPException(
            status_code=409, detail=f"account name already in use"
        )
    await db.commit()
    await db.refresh(acc)
    return AccountOut.model_validate(acc)


@router.post("/{account_id}/archive", response_model=AccountOut)
async def archive_endpoint(
    account_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> AccountOut:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc = await archive_account(db, acc)
    await db.commit()
    return AccountOut.model_validate(acc)


@router.post("/{account_id}/unarchive", response_model=AccountOut)
async def unarchive_endpoint(
    account_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> AccountOut:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc = await unarchive_account(db, acc)
    await db.commit()
    return AccountOut.model_validate(acc)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    account_id: uuid.UUID, _user: CurrentUser, db: DbSession
) -> None:
    acc = await get_account(db, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        await delete_account(db, acc)
    except AccountInUseError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"account in use: {exc.n_trades} trades, {exc.n_snapshots} "
                "snapshots reference it. Archive it instead."
            ),
        )
    await db.commit()

"""Tags CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.problem_details import conflict, not_found
from app.models import Tag, TradeTag
from app.schemas.tag import TagCreate, TagOut, TagUpdate, TagWithUsage

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagWithUsage])
async def list_tags(_user: CurrentUser, db: DbSession) -> list[TagWithUsage]:
    res = await db.execute(
        select(Tag, func.count(TradeTag.trade_id))
        .outerjoin(TradeTag, TradeTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    return [
        TagWithUsage(
            id=tag.id,
            name=tag.name,
            color_hex=tag.color_hex,
            created_at=tag.created_at,
            n_trades=int(count),
        )
        for tag, count in res.all()
    ]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(payload: TagCreate, _user: CurrentUser, db: DbSession) -> Tag:
    existing = await db.execute(select(Tag).where(Tag.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise conflict(f"Tag {payload.name!r} already exists.")
    tag = Tag(name=payload.name, color_hex=payload.color_hex)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.patch("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: uuid.UUID, payload: TagUpdate, _user: CurrentUser, db: DbSession
) -> Tag:
    res = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = res.scalar_one_or_none()
    if tag is None:
        raise not_found(f"Tag {tag_id} does not exist.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != tag.name:
        clash = await db.execute(select(Tag.id).where(Tag.name == data["name"]))
        if clash.scalar_one_or_none() is not None:
            raise conflict(f"Tag {data['name']!r} already exists.")
    for k, v in data.items():
        setattr(tag, k, v)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: uuid.UUID, _user: CurrentUser, db: DbSession) -> None:
    res = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = res.scalar_one_or_none()
    if tag is None:
        raise not_found(f"Tag {tag_id} does not exist.")
    await db.delete(tag)
    await db.commit()

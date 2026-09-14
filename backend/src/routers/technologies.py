from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.deps import get_current_user, require_admin
from src.models import Resource, ResourceStatus, Technology, User
from src.schemas import TechnologyCreate, TechnologyOut, TechnologyUpdate
from src.services.lookups import get_technology_or_404
from src.services.slugs import slugify

router = APIRouter(prefix="/technologies", tags=["technologies"])


async def _unique_slug(db: AsyncSession, name: str, exclude_id: int | None = None) -> str:
    base = slugify(name)
    slug = base
    suffix = 2
    while True:
        query = select(Technology.id).where(Technology.slug == slug)
        if exclude_id is not None:
            query = query.where(Technology.id != exclude_id)
        existing = await db.execute(query)
        if existing.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


async def _to_out(db: AsyncSession, tech: Technology) -> TechnologyOut:
    count_result = await db.execute(
        select(func.count()).select_from(Resource).where(
            Resource.technology_id == tech.id, Resource.status == ResourceStatus.ready
        )
    )
    ready_count = count_result.scalar_one()
    return TechnologyOut(
        id=tech.id,
        name=tech.name,
        slug=tech.slug,
        description=tech.description,
        ready_resource_count=ready_count,
        created_at=tech.created_at,
    )


@router.get("", response_model=list[TechnologyOut])
async def list_technologies(
    db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[TechnologyOut]:
    result = await db.execute(select(Technology).order_by(Technology.name))
    techs = result.scalars().all()
    return [await _to_out(db, t) for t in techs]


@router.post("", response_model=TechnologyOut, status_code=status.HTTP_201_CREATED)
async def create_technology(
    body: TechnologyCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
) -> TechnologyOut:
    existing = await db.execute(select(Technology).where(Technology.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A technology with this name already exists")

    slug = await _unique_slug(db, body.name)
    tech = Technology(name=body.name, slug=slug, description=body.description, created_by=admin.id)
    db.add(tech)
    await db.commit()
    await db.refresh(tech)
    return await _to_out(db, tech)


@router.get("/{technology_id}", response_model=TechnologyOut)
async def get_technology(
    technology_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> TechnologyOut:
    tech = await get_technology_or_404(db, technology_id)
    return await _to_out(db, tech)


@router.patch("/{technology_id}", response_model=TechnologyOut)
async def update_technology(
    technology_id: int,
    body: TechnologyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TechnologyOut:
    tech = await get_technology_or_404(db, technology_id)
    if body.name is not None and body.name != tech.name:
        existing = await db.execute(
            select(Technology).where(Technology.name == body.name, Technology.id != technology_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "A technology with this name already exists")
        tech.name = body.name
        tech.slug = await _unique_slug(db, body.name, exclude_id=technology_id)
    if body.description is not None:
        tech.description = body.description
    await db.commit()
    await db.refresh(tech)
    return await _to_out(db, tech)


@router.delete("/{technology_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technology(
    technology_id: int, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
) -> None:
    tech = await get_technology_or_404(db, technology_id)
    await db.delete(tech)
    await db.commit()

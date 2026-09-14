from typing import Protocol

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.deps import require_admin
from src.models import Resource, ResourceStatus, User
from src.schemas import ResourceBatchResult, ResourceCreateBatch, ResourceOut
from src.services.lookups import get_resource_or_404, get_technology_or_404
from src.services.slugs import normalize_url

router = APIRouter(tags=["resources"])


class IngestionTrigger(Protocol):
    def __call__(self, resource_id: int, background_tasks: BackgroundTasks) -> None: ...


def _start_ingestion(resource_id: int, background_tasks: BackgroundTasks) -> None:
    from src.services.ingestion.pipeline import ingest_resource

    background_tasks.add_task(ingest_resource, resource_id)


def get_ingestion_trigger() -> IngestionTrigger:
    """Overridden with a no-op in tests, so `TestClient` requests never perform
    real network fetches or touch the ingestion pipeline's own DB engine.
    """
    return _start_ingestion


@router.get("/technologies/{technology_id}/resources", response_model=list[ResourceOut])
async def list_resources(
    technology_id: int, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[Resource]:
    await get_technology_or_404(db, technology_id)
    result = await db.execute(
        select(Resource).where(Resource.technology_id == technology_id).order_by(Resource.created_at)
    )
    return list(result.scalars().all())


@router.post("/technologies/{technology_id}/resources", response_model=ResourceBatchResult)
async def add_resources(
    technology_id: int,
    body: ResourceCreateBatch,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    trigger_ingestion: IngestionTrigger = Depends(get_ingestion_trigger),
) -> ResourceBatchResult:
    await get_technology_or_404(db, technology_id)

    existing_result = await db.execute(
        select(Resource.normalized_url).where(Resource.technology_id == technology_id)
    )
    existing_normalized = set(existing_result.scalars().all())

    created: list[Resource] = []
    skipped: list[dict] = []
    seen_in_batch: set[str] = set()

    for url in body.urls:
        url_str = str(url)
        normalized = normalize_url(url_str)
        if normalized in existing_normalized or normalized in seen_in_batch:
            skipped.append({"url": url_str, "reason": "duplicate"})
            continue
        seen_in_batch.add(normalized)
        resource = Resource(
            technology_id=technology_id,
            url=url_str,
            normalized_url=normalized,
            status=ResourceStatus.pending,
        )
        db.add(resource)
        created.append(resource)

    await db.commit()
    for resource in created:
        await db.refresh(resource)
        trigger_ingestion(resource.id, background_tasks)

    return ResourceBatchResult(created=created, skipped=skipped)


@router.post("/resources/{resource_id}/reingest", response_model=ResourceOut)
async def reingest_resource(
    resource_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    trigger_ingestion: IngestionTrigger = Depends(get_ingestion_trigger),
) -> Resource:
    resource = await get_resource_or_404(db, resource_id)
    resource.status = ResourceStatus.pending
    resource.error = None
    await db.commit()
    await db.refresh(resource)
    trigger_ingestion(resource.id, background_tasks)
    return resource


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: int, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
) -> None:
    resource = await get_resource_or_404(db, resource_id)
    await db.delete(resource)
    await db.commit()

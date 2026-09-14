"""Shared 404-or-return lookups used by multiple routers."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Resource, Technology


async def get_technology_or_404(db: AsyncSession, technology_id: int) -> Technology:
    tech = await db.get(Technology, technology_id)
    if tech is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Technology not found")
    return tech


async def get_resource_or_404(db: AsyncSession, resource_id: int) -> Resource:
    resource = await db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return resource

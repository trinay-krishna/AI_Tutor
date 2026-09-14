from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.deps import require_admin
from src.models import User
from src.schemas import RetrievalHit, RetrievalSearchRequest
from src.services.lookups import get_technology_or_404
from src.services.retrieval import retrieve

router = APIRouter(tags=["retrieval"])


@router.post("/technologies/{technology_id}/search", response_model=list[RetrievalHit])
async def search_technology(
    technology_id: int,
    body: RetrievalSearchRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[RetrievalHit]:
    """Debug endpoint for admins to inspect retrieval quality and tune the
    similarity threshold; not used by the learner-facing chat.
    """
    await get_technology_or_404(db, technology_id)
    chunks = await retrieve(body.query, technology_id, k=body.k)
    return [
        RetrievalHit(
            chunk_id=str(c.document.id),
            resource_id=int(c.document.metadata.get("resource_id")),
            title=c.document.metadata.get("title"),
            url=c.document.metadata.get("url"),
            heading_path=c.document.metadata.get("heading_path"),
            content=c.document.page_content,
            score=c.score,
        )
        for c in chunks
    ]

"""End-to-end ingestion for a single resource: fetch -> extract -> split -> embed -> store.

Runs as a FastAPI BackgroundTask. Uses a build-then-swap strategy so a failure
partway through never leaves a resource half-indexed: the new Document/chunks are
built and embedded first, and only swapped in (replacing the old ones) once that
succeeds.
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime

from langchain_core.documents import Document as LCDocument
from sqlalchemy import select

from src.db import AsyncSessionLocal
from src.models import Document, Resource, ResourceStatus, Technology
from src.services.ingestion.extractor import ExtractionError, extract_page, to_langchain_document
from src.services.ingestion.fetcher import FetchError, fetch
from src.services.ingestion.splitter import split_document
from src.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(3)


def _content_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _embedding_text(chunk: LCDocument, technology_name: str) -> str:
    """A small context header prepended before embedding (not stored as content)."""
    title = chunk.metadata.get("title") or ""
    heading = chunk.metadata.get("heading_path") or ""
    header = " | ".join(p for p in (technology_name, title, heading) if p)
    return f"{header}\n\n{chunk.page_content}" if header else chunk.page_content


async def ingest_resource(resource_id: int) -> None:
    async with _semaphore:
        async with AsyncSessionLocal() as db:
            resource = await db.get(Resource, resource_id)
            if resource is None:
                logger.warning("ingest_resource: resource %s not found", resource_id)
                return

            resource.status = ResourceStatus.processing
            resource.error = None
            await db.commit()

            technology = await db.get(Technology, resource.technology_id)
            technology_name = technology.name if technology else ""

            try:
                fetched = await fetch(resource.url)
                page = extract_page(fetched.text, fetched.url)
            except (FetchError, ExtractionError) as e:
                await _mark_failed(db, resource_id, str(e))
                return
            except Exception as e:  # noqa: BLE001 -- ingestion must never crash the worker
                logger.exception("ingest_resource fetch/extract failed for resource %s", resource_id)
                await _mark_failed(db, resource_id, f"Unexpected error: {e}")
                return

            base_doc = to_langchain_document(page, fetched.url)
            content_hash = _content_hash(page.markdown)

            new_document = Document(
                id=uuid.uuid4(),
                resource_id=resource.id,
                technology_id=resource.technology_id,
                url=fetched.url,
                title=page.title,
                content=page.markdown,
                outline=page.outline,
                content_hash=content_hash,
            )
            db.add(new_document)
            # Committed (not just flushed): PGVectorStore below writes through its
            # own separate DB connection, which can't see an uncommitted insert
            # made on this session's connection -- the chunks FK to documents
            # would fail otherwise.
            await db.commit()
            await db.refresh(new_document)

            try:
                raw_chunks = split_document(base_doc)
                if not raw_chunks:
                    raise ExtractionError("Content produced no chunks after splitting")

                for chunk in raw_chunks:
                    chunk.metadata["technology_id"] = resource.technology_id
                    chunk.metadata["document_id"] = str(new_document.id)
                    chunk.metadata["resource_id"] = resource.id
                    chunk.metadata.setdefault("title", page.title)
                    chunk.metadata.setdefault("url", fetched.url)

                embed_texts = [_embedding_text(c, technology_name) for c in raw_chunks]
                embeddable_chunks = [
                    LCDocument(page_content=text, metadata=c.metadata)
                    for text, c in zip(embed_texts, raw_chunks, strict=True)
                ]

                store = await get_vector_store()
                chunk_ids = [str(uuid.uuid4()) for _ in embeddable_chunks]
                await store.aadd_documents(embeddable_chunks, ids=chunk_ids)

                # Swap: drop the resource's previous document (cascades its old chunks).
                old_result = await db.execute(
                    select(Document).where(
                        Document.resource_id == resource.id, Document.id != new_document.id
                    )
                )
                for old_doc in old_result.scalars().all():
                    await db.delete(old_doc)

                resource.status = ResourceStatus.ready
                resource.title = page.title
                resource.chunk_count = len(embeddable_chunks)
                resource.last_ingested_at = datetime.now(UTC)
                resource.error = None
                await db.commit()

            except (FetchError, ExtractionError) as e:
                await db.delete(new_document)  # cascades any chunks that made it in
                await db.commit()
                await _mark_failed(db, resource_id, str(e))
            except Exception as e:  # noqa: BLE001 -- ingestion must never crash the worker
                logger.exception("ingest_resource failed for resource %s", resource_id)
                await db.delete(new_document)
                await db.commit()
                await _mark_failed(db, resource_id, f"Unexpected error: {e}")


async def _mark_failed(db, resource_id: int, error: str) -> None:
    resource = await db.get(Resource, resource_id)
    if resource is not None:
        resource.status = ResourceStatus.failed
        resource.error = error[:2000]
        await db.commit()


async def recover_interrupted_resources() -> None:
    """Startup recovery: resources stuck in `processing` from a killed worker
    (e.g. `--reload` restart) are marked failed so the admin can retry them.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resource).where(Resource.status == ResourceStatus.processing))
        stuck = result.scalars().all()
        for resource in stuck:
            resource.status = ResourceStatus.failed
            resource.error = "Interrupted before completion -- retry."
        if stuck:
            await db.commit()
            logger.info("Recovered %d interrupted resource(s)", len(stuck))

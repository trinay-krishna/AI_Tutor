"""The PGVectorStore instance, pointed at our own Alembic-managed `chunks` table."""

from functools import lru_cache

from langchain_postgres import PGEngine, PGVectorStore

from src.config import get_settings
from src.services.llm import get_embeddings

METADATA_COLUMNS = [
    "technology_id",
    "document_id",
    "resource_id",
    "heading_path",
    "chunk_index",
    "title",
    "url",
]


@lru_cache
def get_pg_engine() -> PGEngine:
    settings = get_settings()
    return PGEngine.from_connection_string(url=settings.database_url)


async def get_vector_store() -> PGVectorStore:
    return await PGVectorStore.create(
        engine=get_pg_engine(),
        embedding_service=get_embeddings(),
        table_name="chunks",
        content_column="content",
        embedding_column="embedding",
        id_column="id",
        metadata_columns=METADATA_COLUMNS,
        metadata_json_column="langchain_metadata",
    )

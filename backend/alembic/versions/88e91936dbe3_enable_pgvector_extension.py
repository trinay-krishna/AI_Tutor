"""enable pgvector extension

Revision ID: 88e91936dbe3
Revises: 
Create Date: 2026-09-12 20:16:15.220616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88e91936dbe3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Filtered HNSW searches (WHERE technology_id = ...) can otherwise under-return
    # once a technology's chunks are a small fraction of the index.
    dbname = op.get_bind().engine.url.database
    op.execute(f'ALTER DATABASE "{dbname}" SET hnsw.iterative_scan = \'relaxed_order\'')


def downgrade() -> None:
    """Downgrade schema."""
    dbname = op.get_bind().engine.url.database
    op.execute(f'ALTER DATABASE "{dbname}" RESET hnsw.iterative_scan')
    op.execute("DROP EXTENSION IF EXISTS vector")

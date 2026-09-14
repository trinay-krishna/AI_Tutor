"""Heading-aware chunking: MarkdownHeaderTextSplitter -> token-bounded splitter."""

import re

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from src.config import get_settings

settings = get_settings()

_HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _clean_heading_text(text: str) -> str:
    # Some pages render deeper headings (h4+) or icon-prefixed callouts as literal
    # "#### " text inside an h1-h3 section (not a split boundary); strip that so it
    # doesn't leak into the displayed heading path.
    return re.sub(r"^#+\s*", "", text).strip()


def _heading_path(metadata: dict) -> str | None:
    parts = [_clean_heading_text(metadata[key]) for key in ("h1", "h2", "h3") if metadata.get(key)]
    return " > ".join(p for p in parts if p) or None


def split_document(doc: LCDocument) -> list[LCDocument]:
    """Split a cleaned markdown Document into embeddable chunks.

    Each output chunk carries `heading_path`, `chunk_index`, `title`, `url` in its
    metadata (on top of whatever the input document already had), ready to hand to
    the vector store.
    """
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = header_splitter.split_text(doc.page_content)

    token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
    )

    chunks: list[LCDocument] = []
    for section in sections:
        heading_path = _heading_path(section.metadata)
        pieces = token_splitter.split_text(section.page_content)
        for piece in pieces:
            text = piece.strip()
            if not text:
                continue
            chunks.append(
                LCDocument(
                    page_content=text,
                    metadata={
                        **doc.metadata,
                        "heading_path": heading_path,
                    },
                )
            )

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks

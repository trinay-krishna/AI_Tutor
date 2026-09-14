"""HTML -> cleaned markdown extraction using trafilatura."""

import re
from dataclasses import dataclass

import trafilatura
from langchain_core.documents import Document as LCDocument
from trafilatura.metadata import extract_metadata

from src.config import get_settings

settings = get_settings()

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


class ExtractionError(Exception):
    """Raised when a page yields no usable content (e.g. JS-only pages)."""


@dataclass
class ExtractedPage:
    title: str
    markdown: str
    outline: list[dict]  # [{"level": 1, "text": "..."}]


def _build_outline(markdown: str) -> list[dict]:
    return [
        {"level": len(m.group(1)), "text": m.group(2).strip()}
        for m in _HEADING_RE.finditer(markdown)
    ]


def extract_page(html: str, url: str) -> ExtractedPage:
    markdown = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_formatting=True,
        include_tables=True,
        favor_recall=True,
    )

    if not markdown or len(markdown.strip()) < settings.ingestion_min_content_chars:
        raise ExtractionError("No readable content -- page may require JavaScript.")

    metadata = extract_metadata(html, default_url=url)
    title = (metadata.title if metadata and metadata.title else None) or url

    return ExtractedPage(title=title, markdown=markdown.strip(), outline=_build_outline(markdown))


def to_langchain_document(page: ExtractedPage, url: str) -> LCDocument:
    return LCDocument(page_content=page.markdown, metadata={"url": url, "title": page.title})

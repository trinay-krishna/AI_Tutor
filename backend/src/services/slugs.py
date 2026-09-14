"""Slug and URL normalization helpers."""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "technology"


def normalize_url(url: str) -> str:
    """Drop the fragment and trailing slash, lowercase the host, for de-duplication."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or ""
    return urlunsplit((scheme, netloc, path, parts.query, ""))

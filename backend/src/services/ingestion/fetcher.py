"""Safe URL fetching: SSRF guard, redirect re-validation, robots.txt, size caps."""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from src.config import get_settings

settings = get_settings()

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "text/markdown", "application/xhtml+xml")
USER_AGENT = "AI-Tutor-Ingestion/1.0 (+https://github.com/; educational tutor bot)"
MAX_REDIRECTS = 5


class FetchError(Exception):
    """Raised for any ingestion-stopping fetch problem; message is admin-facing."""


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    content_type: str
    text: str


def _is_blocked_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_safe_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise FetchError(f"Unsupported URL scheme: {parts.scheme}")
    if not parts.hostname:
        raise FetchError("URL has no host")

    try:
        addrs = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as e:
        raise FetchError(f"Could not resolve host: {parts.hostname}") from e

    for family, _, _, _, sockaddr in addrs:
        ip_str = sockaddr[0]
        if _is_blocked_ip(ip_str):
            raise FetchError(f"Refusing to fetch a private/internal address ({ip_str})")


async def _check_robots_allowed(client: httpx.AsyncClient, url: str) -> bool:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = await client.get(robots_url, timeout=5)
        if resp.status_code >= 400:
            return True  # no robots.txt -> allowed
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser.can_fetch(USER_AGENT, url)
    except httpx.HTTPError:
        return True  # fail open on robots.txt fetch problems


async def fetch(url: str) -> FetchResult:
    """Fetch `url`, following redirects manually so every hop is SSRF-checked."""
    current_url = url
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=settings.ingestion_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        if not await _check_robots_allowed(client, current_url):
            raise FetchError("Blocked by robots.txt")

        for _ in range(MAX_REDIRECTS + 1):
            _assert_safe_host(current_url)

            async with client.stream("GET", current_url) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise FetchError("Redirect with no Location header")
                    current_url = urljoin(current_url, location)
                    continue

                if resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code} fetching {current_url}")

                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type and not any(content_type.startswith(t) for t in ALLOWED_CONTENT_TYPES):
                    raise FetchError(f"Unsupported content type: {content_type}")

                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.ingestion_max_body_bytes:
                        raise FetchError("Page exceeds the size limit")

                encoding = resp.encoding or "utf-8"
                text = body.decode(encoding, errors="replace")
                return FetchResult(url=current_url, content_type=content_type, text=text)

        raise FetchError("Too many redirects")

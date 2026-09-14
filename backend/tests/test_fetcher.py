import pytest

from src.services.ingestion.fetcher import FetchError, _assert_safe_host


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/",  # cloud metadata endpoint
        "http://[::1]/",
    ],
)
def test_blocks_private_and_loopback_addresses(url):
    with pytest.raises(FetchError):
        _assert_safe_host(url)


@pytest.mark.parametrize("url", ["ftp://example.com/file", "file:///etc/passwd", "javascript:alert(1)"])
def test_blocks_disallowed_schemes(url):
    with pytest.raises(FetchError):
        _assert_safe_host(url)


def test_allows_public_host():
    # example.com resolves to a public IP; this only checks DNS + scheme, no network fetch.
    _assert_safe_host("https://example.com/page")

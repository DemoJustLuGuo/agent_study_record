import pytest

from rag.ingest.web_loader import normalize_web_url, validate_web_url_allowed


def test_normalize_web_url_rejects_non_http_urls() -> None:
    assert normalize_web_url("file:///etc/passwd") == ""
    assert normalize_web_url("ftp://example.com/file") == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.0.0.1",
        "http://192.168.1.10",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
    ],
)
def test_validate_web_url_blocks_private_or_local_targets(url: str) -> None:
    with pytest.raises(RuntimeError, match="blocked_private_or_local_address"):
        validate_web_url_allowed(url)

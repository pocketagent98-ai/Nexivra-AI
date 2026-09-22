import pytest

from nexivra.ssrf import UnsafeUrlError, assert_safe_url


def test_allows_public_https():
    check = assert_safe_url("https://example.com/docs", resolve_dns=False)
    assert check.host == "example.com"
    assert not check.is_ip


def test_blocks_private_ipv4():
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("http://192.168.1.10/admin", resolve_dns=False)


def test_blocks_loopback_and_metadata():
    for url in ("http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/latest/meta-data/"):
        with pytest.raises(UnsafeUrlError):
            assert_safe_url(url, resolve_dns=False)


def test_blocks_ipv4_mapped_ipv6():
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("http://[::ffff:127.0.0.1]/", resolve_dns=False)


def test_blocks_non_http_scheme():
    for url in ("file:///etc/passwd", "ftp://x", "gopher://x"):
        with pytest.raises(UnsafeUrlError):
            assert_safe_url(url, resolve_dns=False)


def test_blocks_unusual_port():
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("https://example.com:22/", resolve_dns=False)


def test_blocks_internal_suffixes():
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("http://printer.local/", resolve_dns=False)
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("http://db.internal/", resolve_dns=False)


def test_empty_and_oversize_rejected():
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("")
    with pytest.raises(UnsafeUrlError):
        assert_safe_url("https://example.com/" + "a" * 3000)

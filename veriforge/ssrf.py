"""SSRF-safe URL validation for all outbound fetches.

Every URL the system fetches (research pages, PDFs, provider endpoints)
passes through ``assert_safe_url`` first. Retrieved content is untrusted
data: it may be evidence, never authority over system policy.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443, 8000, 8080, 3000}  # app dev ports kept for local use
MAX_URL_LENGTH = 2048


class UnsafeUrlError(ValueError):
    """Raised when a URL points somewhere we refuse to fetch from."""


@dataclass
class UrlCheck:
    url: str
    host: str
    is_ip: bool


def _forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) bypasses naive checks.
        or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None and _forbidden_ip(ip.ipv4_mapped))
    )


def assert_safe_url(url: str, *, resolve_dns: bool = True) -> UrlCheck:
    """Validate a URL against SSRF rules. Raises UnsafeUrlError when unsafe.

    ``resolve_dns=False`` keeps the check offline (tests / dry runs); the
    hostname literal is then checked only when it is already an IP.
    """
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeUrlError("URL empty or too long")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"scheme not allowed: {parsed.scheme!r}")

    host = (parsed.hostname or "").strip("[]")
    if not host:
        raise UnsafeUrlError("URL has no host")

    port = parsed.port
    if port is not None and port not in ALLOWED_PORTS:
        raise UnsafeUrlError(f"port not allowed: {port}")

    is_ip = False
    try:
        ip = ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        ip = None
    if ip is not None and _forbidden_ip(ip):
        raise UnsafeUrlError(f"host is a forbidden address: {host}")
    if ip is None:
        host_norm = host.lower().rstrip(".")
        for bad in ("localhost", "metadata.google.internal", "169.254.169.254"):
            if host_norm == bad:
                raise UnsafeUrlError(f"forbidden host: {host}")
        if host_norm.endswith(".local") or host_norm.endswith(".internal"):
            raise UnsafeUrlError(f"forbidden internal host: {host}")
        if resolve_dns:
            try:
                infos = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80))
            except socket.gaierror as exc:  # pragma: no cover - depends on DNS
                raise UnsafeUrlError(f"cannot resolve host: {host}") from exc
            for info in infos:
                resolved = info[4][0]
                rip = ipaddress.ip_address(resolved)
                if _forbidden_ip(rip):
                    raise UnsafeUrlError(f"host resolves to forbidden address: {host} -> {resolved}")

    return UrlCheck(url=url, host=host, is_ip=is_ip)

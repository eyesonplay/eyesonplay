"""Restrictions on what FFmpeg may open (SSRF / local file disclosure)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from worker.ingest.source import SourceError

NETWORK_PROTOCOLS = "http,https,tcp,tls,crypto,rtmp,rtmps,hls,httpproxy"
FILE_PROTOCOLS = "file"


def protocol_whitelist(is_file: bool) -> str:
    return FILE_PROTOCOLS if is_file else NETWORK_PROTOCOLS


def ensure_public_host(url: str) -> None:
    """Refuse URLs whose host resolves to a private, loopback or link-local address."""
    host = urlsplit(url).hostname
    if not host:
        raise SourceError("stream URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SourceError(f"cannot resolve stream host '{host}'") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise SourceError(f"stream host '{host}' resolves to a non-public address")

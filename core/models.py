from dataclasses import dataclass, field
from datetime import datetime, timezone


class ProxyType:
    HTTP_FORWARD = "Http forward"
    HTTP_CONNECT = "Http connect"
    SOCKS4 = "Socks4"
    SOCKS5 = "Socks 5"
    UNKNOWN = "Unknown"

    ALL = (HTTP_FORWARD, HTTP_CONNECT, SOCKS4, SOCKS5)


@dataclass
class ProxyInfo:
    proxy: str
    proxy_type: str = ProxyType.UNKNOWN
    anonymity_level: str = "Unknown"
    response_time: float = 0.0
    country: str = "Unknown"
    city: str = "Unknown"
    isp: str = "Unknown"
    server_type: str = "Unknown"
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ProxyInfo:
    proxy: str
    proxy_type: str = 'HTTP'
    anonymity_level: str = 'Unknown'
    response_time: float = 0.0
    country: str = 'Unknown'
    city: str = 'Unknown'
    isp: str = 'Unknown'
    server_type: str = 'Unknown'
    last_checked: datetime = field(default_factory=datetime.now)
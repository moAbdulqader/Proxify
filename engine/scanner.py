import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional, Tuple

import aiohttp
from aiohttp_socks import ProxyConnector

from core.config import Config
from core.models import ProxyInfo, ProxyType
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

try:
    import geoip2.database
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False


@dataclass
class ProbeResult:
    success: bool
    response_time: float = 0.0


def select_proxy_type(probes: Dict[str, ProbeResult]) -> Optional[str]:
    preference = (
        ProxyType.SOCKS5,
        ProxyType.SOCKS4,
        ProxyType.HTTP_CONNECT,
        ProxyType.HTTP_FORWARD,
    )
    for proxy_type in preference:
        probe = probes.get(proxy_type)
        if probe and probe.success:
            return proxy_type
    return None


class AdvancedProxyScanner:
    def __init__(self, db: DatabaseManager, stop_event: asyncio.Event):
        self.db = db
        self.stop_event = stop_event
        self.reader = None
        if GEOIP_AVAILABLE and Config.GEO_DB_PATH.exists():
            try:
                self.reader = geoip2.database.Reader(str(Config.GEO_DB_PATH))
            except Exception as exc:
                logger.warning("Failed to load GeoIP database: %s", exc)

    def close(self):
        if self.reader:
            self.reader.close()
            self.reader = None

    def get_geo_info(self, ip: str) -> Tuple[str, str, str, str]:
        country, city = "Unknown", "Unknown"
        if self.reader:
            try:
                ipaddress.ip_address(ip)
                response = self.reader.city(ip)
                country = response.country.name or "Unknown"
                city = response.city.name or "Unknown"
            except (ValueError, Exception):
                pass
        return country, city, "Unknown", "Unknown"

    async def _probe_http(self, proxy: str, url: str) -> ProbeResult:
        started = time.perf_counter()
        try:
            timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
                async with session.get(
                    url,
                    proxy=f"http://{proxy}",
                    allow_redirects=False,
                ) as response:
                    if 200 <= response.status < 400:
                        await response.content.read(1024)
                        return ProbeResult(True, (time.perf_counter() - started) * 1000)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            pass
        return ProbeResult(False, (time.perf_counter() - started) * 1000)

    async def _probe_socks(self, proxy: str, scheme: str) -> ProbeResult:
        started = time.perf_counter()
        connector = None
        try:
            connector = ProxyConnector.from_url(f"{scheme}://{proxy}")
            timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=False) as session:
                async with session.get(
                    Config.SOCKS_TEST_URL,
                    allow_redirects=False,
                    ssl=True,
                ) as response:
                    if 200 <= response.status < 400:
                        await response.content.read(1024)
                        return ProbeResult(True, (time.perf_counter() - started) * 1000)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError):
            pass
        finally:
            if connector and not connector.closed:
                await connector.close()
        return ProbeResult(False, (time.perf_counter() - started) * 1000)

    async def _with_retries(self, probe: Callable[[], Awaitable[ProbeResult]]) -> ProbeResult:
        for attempt in range(Config.SCAN_RETRIES + 1):
            if self.stop_event.is_set():
                return ProbeResult(False)
            result = await probe()
            if result.success or attempt >= Config.SCAN_RETRIES:
                return result
            await asyncio.sleep(Config.RETRY_BACKOFF_SECONDS * (2 ** attempt))
        return ProbeResult(False)

    async def _detect(self, proxy: str) -> Dict[str, ProbeResult]:
        probes = await asyncio.gather(
            self._with_retries(lambda: self._probe_http(proxy, Config.HTTP_FORWARD_TEST_URL)),
            self._with_retries(lambda: self._probe_http(proxy, Config.HTTP_CONNECT_TEST_URL)),
            self._with_retries(lambda: self._probe_socks(proxy, "socks4")),
            self._with_retries(lambda: self._probe_socks(proxy, "socks5")),
            return_exceptions=True,
        )
        keys = (
            ProxyType.HTTP_FORWARD,
            ProxyType.HTTP_CONNECT,
            ProxyType.SOCKS4,
            ProxyType.SOCKS5,
        )
        return {
            key: value if isinstance(value, ProbeResult) else ProbeResult(False)
            for key, value in zip(keys, probes)
        }

    async def _check_proxy(self, proxy: str) -> Optional[ProxyInfo]:
        if self.stop_event.is_set():
            return None
        probes = await self._detect(proxy)
        proxy_type = select_proxy_type(probes)
        if not proxy_type:
            await self.db.mark_dead(proxy)
            return None

        selected = probes[proxy_type]
        host = proxy.rsplit(":", 1)[0]
        country, city, isp, org = self.get_geo_info(host)
        info = ProxyInfo(
            proxy=proxy,
            proxy_type=proxy_type,
            response_time=selected.response_time,
            country=country,
            city=city,
            isp=isp,
            server_type=org,
            anonymity_level="Unknown",
        )
        await self.db.save_proxy(info)
        return info

    async def check_proxy(
        self,
        proxy: str,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> Optional[ProxyInfo]:
        if semaphore:
            async with semaphore:
                return await self._check_proxy(proxy)
        return await self._check_proxy(proxy)

import asyncio
import ipaddress
import logging
import re
from typing import List, Optional, Set

import aiohttp

from core.config import Config

logger = logging.getLogger(__name__)


class ProxyScraper:
    def __init__(self):
        self.pattern = re.compile(
            r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?::|\s+)\d{1,5}(?!\d)"
        )

    def _clean_proxy(self, proxy: str) -> Optional[str]:
        candidate = proxy.strip()
        candidate = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", candidate)
        match = re.match(
            r"^((?:\d{1,3}\.){3}\d{1,3})\s*:\s*(\d{1,5})$", candidate
        ) or re.match(
            r"^((?:\d{1,3}\.){3}\d{1,3})\s+(\d{1,5})$", candidate
        )
        if not match:
            return None

        host, port_text = match.groups()
        try:
            ipaddress.ip_address(host)
            port = int(port_text)
            if 1 <= port <= 65535:
                return f"{host}:{port}"
        except ValueError:
            pass
        return None

    async def fetch_source(self, session: aiohttp.ClientSession, url: str) -> Set[str]:
        proxies = set()
        try:
            timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    logger.warning("Source returned HTTP %s: %s", response.status, url)
                    return proxies
                content = await response.content.read(Config.MAX_DOWNLOAD_SIZE + 1)
                if len(content) > Config.MAX_DOWNLOAD_SIZE:
                    logger.warning("Source exceeded size limit: %s", url)
                    content = content[:Config.MAX_DOWNLOAD_SIZE]
                text = content.decode("utf-8", errors="ignore")
                for match in self.pattern.findall(text):
                    cleaned = self._clean_proxy(match)
                    if cleaned:
                        proxies.add(cleaned)
        except asyncio.TimeoutError:
            logger.warning("Timeout scraping source: %s", url)
        except (aiohttp.ClientError, UnicodeError) as exc:
            logger.warning("Source request failed %s: %s", url, exc)
        except Exception as exc:
            logger.error("Unexpected scraping error %s: %s", url, exc)
        return proxies

    async def scrape_all(self) -> List[str]:
        all_proxies = set()
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            results = await asyncio.gather(
                *(self.fetch_source(session, url) for url in Config.PROXY_SOURCES),
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, set):
                all_proxies.update(result)
        return sorted(all_proxies)

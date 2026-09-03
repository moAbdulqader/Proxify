import re
import logging
import asyncio
import aiohttp
from typing import Set, List, Optional
from core.config import Config

logger = logging.getLogger(__name__)

class ProxyScraper:
    def __init__(self):
        # Pre-compile Regex patterns for high performance
        self.patterns = [
            re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}\b'),
            re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s+\d{2,5}\b')
        ]

    def _clean_proxy(self, proxy: str) -> Optional[str]:
        """Normalize proxy string and validate numerical bounds."""
        proxy = proxy.replace('http://', '').replace('https://', '').replace(' ', ':').replace('\t', ':')
        
        try:
            ip, port = proxy.split(':')
            if all(0 <= int(part) <= 255 for part in ip.split('.')) and 1 <= int(port) <= 65535:
                return proxy
        except ValueError:
            pass
            
        return None

    async def fetch_source(self, session: aiohttp.ClientSession, url: str) -> Set[str]:
        """Fetch and extract proxies from a specific source."""
        proxies = set()
        try:
            async with session.get(url, timeout=Config.REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    # Enforce strict 5MB limit to mitigate Zip Bomb/Memory exhaustion attacks
                    content = await response.content.read(Config.MAX_DOWNLOAD_SIZE)
                    text = content.decode('utf-8', errors='ignore')
                    
                    for pattern in self.patterns:
                        for match in pattern.findall(text):
                            cleaned = self._clean_proxy(match)
                            if cleaned:
                                proxies.add(cleaned)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping source: {url}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            
        return proxies

    async def scrape_all(self) -> List[str]:
        """Concurrently scrape all defined sources."""
        all_proxies = set()
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_source(session, url) for url in Config.PROXY_SOURCES]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result_set in results:
                if isinstance(result_set, set):
                    all_proxies.update(result_set)
                    
        return list(all_proxies)
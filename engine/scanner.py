import time
import logging
import asyncio
import aiohttp
from typing import Optional, Tuple
from aiohttp_socks import ProxyConnector

from core.config import Config
from core.models import ProxyInfo
from database.db_manager import DatabaseManager

# Try loading GeoIP2, fallback gracefully
try:
    import geoip2.database
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False

logger = logging.getLogger(__name__)

class AdvancedProxyScanner:
    def __init__(self, db: DatabaseManager, stop_event: asyncio.Event):
        self.db = db
        self.stop_event = stop_event
        self.reader = None
        
        # Load local database to avoid remote API rate-limits and tracking
        if GEOIP_AVAILABLE and Config.GEO_DB_PATH.exists():
            try:
                self.reader = geoip2.database.Reader(str(Config.GEO_DB_PATH))
            except Exception as e:
                logger.error(f"Failed to load GeoIP Database: {e}")
                self.reader = None

    def get_geo_info(self, ip: str) -> Tuple[str, str, str, str]:
        """Fetch Geolocation locally in microseconds without network I/O."""
        country, city = 'Unknown', 'Unknown'
        
        if self.reader:
            try:
                response = self.reader.city(ip)
                country = response.country.name or 'Unknown'
                city = response.city.name or 'Unknown'
            except Exception:
                pass
                
        return country, city, 'Unknown', 'Unknown' # Org/ISP requires ASN database
        
    async def check_proxy(self, proxy: str, proxy_type: str, semaphore: asyncio.Semaphore) -> Optional[ProxyInfo]:
        """Validate an individual proxy securely."""
        if self.stop_event.is_set():
            return None
            
        async with semaphore:
            success_count = 0
            response_times = []
            
            # Use HTTPS targets to prevent MITM manipulation during tests
            test_urls = [
                ('https://api.ipify.org?format=json', 'HTTPS'),
                ('https://api.myip.com', 'HTTPS')
            ]

            try:
                connector = ProxyConnector.from_url(f"{proxy_type.lower()}://{proxy}")
                # Timeout is set per proxy connection
                timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
                
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    for url, _ in test_urls:
                        if self.stop_event.is_set():
                            break
                            
                        try:
                            start_time = time.time()
                            # Perform SSL validation to ensure endpoint integrity
                            async with session.get(url, ssl=True) as resp:
                                if resp.status == 200:
                                    success_count += 1
                                    response_times.append((time.time() - start_time) * 1000)
                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            continue

                if success_count > 0:
                    avg_time = sum(response_times) / len(response_times)
                    ip = proxy.split(':')[0]
                    
                    country, city, isp, org = self.get_geo_info(ip)
                    
                    info = ProxyInfo(
                        proxy=proxy,
                        proxy_type='HTTPS' if success_count > 1 else 'HTTP',
                        response_time=avg_time,
                        country=country,
                        city=city,
                        isp=isp,
                        server_type=org,
                        anonymity_level="Elite" if success_count > 1 else "Anonymous"
                    )
                    await self.db.save_proxy(info)
                    return info
                else:
                    await self.db.mark_dead(proxy)

            except Exception as e:
                logger.debug(f"Proxy check failed for {proxy}: {e}")
                await self.db.mark_dead(proxy)
                
            return None
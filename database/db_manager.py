import logging
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict
from core.config import Config
from core.models import ProxyInfo

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self.lock = asyncio.Lock()

    async def initialize(self):
        """Asynchronously initialize the database schema."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS proxy_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy TEXT UNIQUE,
                    proxy_type TEXT,
                    anonymity_level TEXT,
                    response_time REAL,
                    country TEXT,
                    city TEXT,
                    isp TEXT,
                    server_type TEXT,
                    last_checked TIMESTAMP,
                    check_count INTEGER DEFAULT 1,
                    success_count INTEGER DEFAULT 1,
                    fail_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            ''')
            # Create indexes for high-performance querying
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON proxy_archive(status)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON proxy_archive(proxy_type)')
            await conn.commit()

    async def save_proxy(self, proxy_info: ProxyInfo):
        """Save or update a working proxy safely."""
        async with self.lock:
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    await conn.execute('''
                        INSERT OR REPLACE INTO proxy_archive 
                        (proxy, proxy_type, anonymity_level, response_time, country, city, isp, server_type, last_checked, status, check_count, success_count, fail_count)
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active',
                            COALESCE((SELECT check_count FROM proxy_archive WHERE proxy = ?) + 1, 1),
                            COALESCE((SELECT success_count FROM proxy_archive WHERE proxy = ?) + 1, 1),
                            COALESCE((SELECT fail_count FROM proxy_archive WHERE proxy = ?), 0)
                        )
                    ''', (
                        proxy_info.proxy, proxy_info.proxy_type, proxy_info.anonymity_level,
                        proxy_info.response_time, proxy_info.country, proxy_info.city,
                        proxy_info.isp, proxy_info.server_type, datetime.now().isoformat(),
                        proxy_info.proxy, proxy_info.proxy, proxy_info.proxy
                    ))
                    await conn.commit()
            except Exception as e:
                logger.error(f"Failed to save proxy {proxy_info.proxy}: {e}")

    async def mark_dead(self, proxy: str):
        """Mark a proxy as dead in the database."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('''
                    UPDATE proxy_archive 
                    SET status='dead', 
                        fail_count=fail_count+1, 
                        check_count=check_count+1,
                        last_checked=?
                    WHERE proxy=?
                ''', (datetime.now().isoformat(), proxy))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark dead proxy {proxy}: {e}")

    async def filter_proxies_to_scan(self, raw_proxies: List[str]) -> List[str]:
        """
        Smart Cooldown Check (TTL Mechanism).
        Optimized to use memory-efficient chunked queries instead of fetching the whole DB.
        """
        proxies_to_scan = []
        now = datetime.now()
        chunk_size = 900  # SQLite limit is 999 parameters
        
        for i in range(0, len(raw_proxies), chunk_size):
            chunk = raw_proxies[i:i + chunk_size]
            placeholders = ','.join('?' for _ in chunk)
            query = f"SELECT proxy, status, last_checked FROM proxy_archive WHERE proxy IN ({placeholders})"
            
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    async with conn.execute(query, chunk) as cursor:
                        rows = await cursor.fetchall()
                        
                db_state = {row[0]: (row[1], row[2]) for row in rows}
                
                for proxy in chunk:
                    if proxy not in db_state:
                        proxies_to_scan.append(proxy)
                        continue
                        
                    status, last_checked_str = db_state[proxy]
                    try:
                        last_checked = datetime.fromisoformat(last_checked_str)
                        delta = now - last_checked
                        
                        if status == 'active' and delta < timedelta(hours=2):
                            continue
                        if status == 'dead' and delta < timedelta(hours=12):
                            continue
                            
                        proxies_to_scan.append(proxy)
                    except (ValueError, TypeError):
                        proxies_to_scan.append(proxy)
            except Exception as e:
                logger.error(f"Error filtering proxies: {e}")
                proxies_to_scan.extend(chunk)  # On failure, scan them anyway
                
        return proxies_to_scan

    async def get_stats(self) -> Dict:
        """Asynchronously retrieve database statistics."""
        stats = {
            'total_in_db': 0,
            'total_working': 0,
            'by_type': defaultdict(int),
            'by_anonymity': defaultdict(int),
            'by_country': defaultdict(int)
        }
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.execute("SELECT COUNT(*) FROM proxy_archive") as cursor:
                    stats['total_in_db'] = (await cursor.fetchone())[0]
                    
                async with conn.execute("SELECT COUNT(*) FROM proxy_archive WHERE status='active'") as cursor:
                    stats['total_working'] = (await cursor.fetchone())[0]
                    
                async with conn.execute("SELECT proxy_type, COUNT(*) FROM proxy_archive WHERE status='active' GROUP BY proxy_type") as cursor:
                    for p_type, count in await cursor.fetchall():
                        stats['by_type'][p_type] = count
                        
                async with conn.execute("SELECT anonymity_level, COUNT(*) FROM proxy_archive WHERE status='active' GROUP BY anonymity_level") as cursor:
                    for anon, count in await cursor.fetchall():
                        stats['by_anonymity'][anon] = count
                        
                async with conn.execute("SELECT country, COUNT(*) FROM proxy_archive WHERE status='active' AND country != 'Unknown' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10") as cursor:
                    for country, count in await cursor.fetchall():
                        stats['by_country'][country] = count
        except Exception as e:
            logger.error(f"Database statistics error: {e}")
            
        return stats
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import aiosqlite

from core.config import Config
from core.models import ProxyInfo, ProxyType

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self.lock = asyncio.Lock()

    def _connection(self):
        return aiosqlite.connect(
            self.db_path,
            timeout=Config.SQLITE_BUSY_TIMEOUT_MS / 1000,
        )

    async def _configure_connection(self, conn):
        await conn.execute(f"PRAGMA busy_timeout = {Config.SQLITE_BUSY_TIMEOUT_MS}")

    async def initialize(self):
        async with self._connection() as conn:
            await self._configure_connection(conn)
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS proxy_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy TEXT UNIQUE,
                    proxy_type TEXT NOT NULL DEFAULT 'Unknown',
                    anonymity_level TEXT NOT NULL DEFAULT 'Unknown',
                    response_time REAL NOT NULL DEFAULT 0,
                    country TEXT NOT NULL DEFAULT 'Unknown',
                    city TEXT NOT NULL DEFAULT 'Unknown',
                    isp TEXT NOT NULL DEFAULT 'Unknown',
                    server_type TEXT NOT NULL DEFAULT 'Unknown',
                    last_checked TIMESTAMP NOT NULL,
                    check_count INTEGER DEFAULT 1,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON proxy_archive(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON proxy_archive(proxy_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_last_checked ON proxy_archive(last_checked)")
            await conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def save_proxy(self, proxy_info: ProxyInfo):
        async with self.lock:
            try:
                async with self._connection() as conn:
                    await self._configure_connection(conn)
                    await conn.execute("""
                        INSERT INTO proxy_archive (
                            proxy, proxy_type, anonymity_level, response_time,
                            country, city, isp, server_type, last_checked,
                            status, check_count, success_count, fail_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 1, 0)
                        ON CONFLICT(proxy) DO UPDATE SET
                            proxy_type=excluded.proxy_type,
                            anonymity_level=excluded.anonymity_level,
                            response_time=excluded.response_time,
                            country=excluded.country,
                            city=excluded.city,
                            isp=excluded.isp,
                            server_type=excluded.server_type,
                            last_checked=excluded.last_checked,
                            status='active',
                            check_count=proxy_archive.check_count + 1,
                            success_count=proxy_archive.success_count + 1
                    """, (
                        proxy_info.proxy,
                        proxy_info.proxy_type,
                        proxy_info.anonymity_level,
                        proxy_info.response_time,
                        proxy_info.country,
                        proxy_info.city,
                        proxy_info.isp,
                        proxy_info.server_type,
                        self._now(),
                    ))
                    await conn.commit()
            except Exception as exc:
                logger.error("Failed to save proxy %s: %s", proxy_info.proxy, exc)

    async def mark_dead(self, proxy: str):
        async with self.lock:
            try:
                async with self._connection() as conn:
                    await self._configure_connection(conn)
                    await conn.execute("""
                        INSERT INTO proxy_archive (
                            proxy, proxy_type, anonymity_level, response_time,
                            country, city, isp, server_type, last_checked,
                            status, check_count, success_count, fail_count
                        ) VALUES (?, 'Unknown', 'Unknown', 0, 'Unknown', 'Unknown', 'Unknown', 'Unknown', ?, 'dead', 1, 0, 1)
                        ON CONFLICT(proxy) DO UPDATE SET
                            last_checked=excluded.last_checked,
                            status='dead',
                            check_count=proxy_archive.check_count + 1,
                            fail_count=proxy_archive.fail_count + 1
                    """, (proxy, self._now()))
                    await conn.commit()
            except Exception as exc:
                logger.error("Failed to mark dead proxy %s: %s", proxy, exc)

    async def filter_proxies_to_scan(self, raw_proxies: List[str]) -> List[str]:
        if not raw_proxies:
            return []

        proxies_to_scan = []
        now = datetime.now(timezone.utc)
        chunk_size = 900

        try:
            async with self._connection() as conn:
                await self._configure_connection(conn)
                for start in range(0, len(raw_proxies), chunk_size):
                    chunk = raw_proxies[start:start + chunk_size]
                    placeholders = ",".join("?" for _ in chunk)
                    query = f"SELECT proxy, status, last_checked FROM proxy_archive WHERE proxy IN ({placeholders})"
                    async with conn.execute(query, chunk) as cursor:
                        rows = await cursor.fetchall()
                    db_state = {row[0]: (row[1], row[2]) for row in rows}

                    for proxy in chunk:
                        if proxy not in db_state:
                            proxies_to_scan.append(proxy)
                            continue
                        status, last_checked_value = db_state[proxy]
                        try:
                            last_checked = datetime.fromisoformat(last_checked_value)
                            if last_checked.tzinfo is None:
                                last_checked = last_checked.replace(tzinfo=timezone.utc)
                            age = now - last_checked
                            if status == "active" and age < timedelta(hours=2):
                                continue
                            if status == "dead" and age < timedelta(hours=12):
                                continue
                        except (TypeError, ValueError):
                            pass
                        proxies_to_scan.append(proxy)
        except Exception as exc:
            logger.error("Error filtering proxies: %s", exc)
            return list(raw_proxies)

        return proxies_to_scan

    async def get_stats(self) -> Dict:
        stats = {
            "total_in_db": 0,
            "total_working": 0,
            "by_type": defaultdict(int),
            "by_anonymity": defaultdict(int),
            "by_country": defaultdict(int),
        }
        try:
            async with self._connection() as conn:
                await self._configure_connection(conn)
                async with conn.execute("SELECT COUNT(*), SUM(status = 'active') FROM proxy_archive") as cursor:
                    total, active = await cursor.fetchone()
                    stats["total_in_db"] = total or 0
                    stats["total_working"] = active or 0
                async with conn.execute("SELECT proxy_type, COUNT(*) FROM proxy_archive WHERE status='active' GROUP BY proxy_type") as cursor:
                    for proxy_type, count in await cursor.fetchall():
                        stats["by_type"][proxy_type] = count
                async with conn.execute("SELECT anonymity_level, COUNT(*) FROM proxy_archive WHERE status='active' GROUP BY anonymity_level") as cursor:
                    for anonymity, count in await cursor.fetchall():
                        stats["by_anonymity"][anonymity] = count
                async with conn.execute("SELECT country, COUNT(*) FROM proxy_archive WHERE status='active' AND country != 'Unknown' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10") as cursor:
                    for country, count in await cursor.fetchall():
                        stats["by_country"][country] = count
        except Exception as exc:
            logger.error("Database statistics error: %s", exc)
        return stats

    async def get_active_proxies(self) -> List[str]:
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("SELECT proxy FROM proxy_archive WHERE status='active' ORDER BY proxy") as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_category_stats(self):
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("""
                SELECT proxy_type, anonymity_level, COUNT(*)
                FROM proxy_archive
                WHERE status='active'
                GROUP BY proxy_type, anonymity_level
                ORDER BY proxy_type, anonymity_level
            """) as cursor:
                return await cursor.fetchall()

    async def get_country_stats(self):
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("""
                SELECT country, COUNT(*)
                FROM proxy_archive
                WHERE status='active' AND country != 'Unknown'
                GROUP BY country
                ORDER BY COUNT(*) DESC LIMIT 15
            """) as cursor:
                return await cursor.fetchall()

    async def get_detailed_stats(self) -> Dict:
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("""
                SELECT
                    COUNT(*),
                    SUM(status = 'active'),
                    SUM(status = 'dead'),
                    AVG(CASE WHEN status='active' AND response_time > 0 THEN response_time END),
                    COALESCE(SUM(success_count), 0),
                    COALESCE(SUM(check_count), 0)
                FROM proxy_archive
            """) as cursor:
                total, active, dead, average, successes, checks = await cursor.fetchone()
        return {
            "total": total or 0,
            "active": active or 0,
            "dead": dead or 0,
            "average_latency": average or 0.0,
            "successes": successes or 0,
            "checks": checks or 0,
            "success_rate": (successes / checks * 100) if checks else 0.0,
        }

    async def get_active_by_type(self, proxy_type: str) -> List[str]:
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("SELECT proxy FROM proxy_archive WHERE proxy_type=? AND status='active' ORDER BY proxy", (proxy_type,)) as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_active_by_anonymity(self, anonymity: str) -> List[str]:
        async with self._connection() as conn:
            await self._configure_connection(conn)
            async with conn.execute("SELECT proxy FROM proxy_archive WHERE anonymity_level=? AND status='active' ORDER BY proxy", (anonymity,)) as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def purge(self):
        async with self.lock:
            async with self._connection() as conn:
                await self._configure_connection(conn)
                await conn.execute("DELETE FROM proxy_archive")
                await conn.commit()

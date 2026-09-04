import asyncio

from core.models import ProxyInfo, ProxyType
from core.config import Config
from database.db_manager import DatabaseManager


def test_database_tracks_success_and_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "proxy.db"
    monkeypatch.setattr(Config, "DB_PATH", db_path)

    async def scenario():
        db = DatabaseManager()
        await db.initialize()
        await db.save_proxy(ProxyInfo("1.2.3.4:8080", proxy_type=ProxyType.SOCKS5, response_time=25))
        await db.save_proxy(ProxyInfo("1.2.3.4:8080", proxy_type=ProxyType.SOCKS5, response_time=20))
        stats = await db.get_detailed_stats()
        assert stats["total"] == 1
        assert stats["active"] == 1
        assert stats["checks"] == 2
        assert stats["successes"] == 2

        await db.mark_dead("1.2.3.4:8080")
        stats = await db.get_detailed_stats()
        assert stats["dead"] == 1
        assert await db.filter_proxies_to_scan(["1.2.3.4:8080"]) == []

    asyncio.run(scenario())

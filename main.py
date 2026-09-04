#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys

from core.config import Config
from database.db_manager import DatabaseManager
from engine.scanner import AdvancedProxyScanner
from engine.scraper import ProxyScraper
from ui.cli import ProxyMasterController


async def main():
    stop_event = asyncio.Event()
    db = DatabaseManager()
    await db.initialize()
    scanner = AdvancedProxyScanner(db, stop_event)
    controller = ProxyMasterController(db, ProxyScraper(), scanner, stop_event)
    try:
        await controller.run()
    finally:
        scanner.close()


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted. Exited cleanly.")
        sys.exit(0)
    except Exception as exc:
        print(f"\n[!] Critical startup failure: {exc}")
        sys.exit(1)

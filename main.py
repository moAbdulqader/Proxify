#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import asyncio

from core.config import Config
from database.db_manager import DatabaseManager
from engine.scraper import ProxyScraper
from engine.scanner import AdvancedProxyScanner
from ui.cli import ProxyMasterController

async def main():
    # Setup global stop event for graceful asynchronous exits
    stop_event = asyncio.Event()

    # Initialize Core Components
    db = DatabaseManager()
    await db.initialize()
    
    scraper = ProxyScraper()
    scanner = AdvancedProxyScanner(db, stop_event)
    
    # Initialize and run UI Controller
    controller = ProxyMasterController(db, scraper, scanner, stop_event)
    
    try:
        await controller.run()
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    # Performance & Compatibility Policy setup
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        # Run main event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Program interrupted by user. Exited cleanly.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Critical Startup Failure: {e}")
        sys.exit(1)
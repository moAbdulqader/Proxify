# Proxy Master Elite - Unified Edition

A production-ready proxy scraping, scanning, and archiving system built with Python and AsyncIO.

## Features
- **High Performance:** Fully asynchronous operations using `aiohttp` and `aiosqlite`.
- **Local GeoIP Routing:** Blazing fast offline location resolution using MaxMind `GeoLite2-City.mmdb`.
- **Smart Filtering:** Built-in TTL cooldowns to prevent redundant scanning.
- **Rich UI:** Beautiful command-line interface with live progress bars.

## Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
# Proxify - Proxy Classification Engine

Proxify is an asynchronous command-line tool that collects public proxy endpoints, verifies them, classifies their working protocol, and archives the results in SQLite.

## Detected proxy types

Each candidate is tested independently and classified as one of:

- Http forward: HTTP requests through an HTTP proxy.
- Http connect: HTTPS tunneling through an HTTP proxy using CONNECT.
- Socks4: HTTPS access through a SOCKS4 proxy.
- Socks 5: HTTPS access through a SOCKS5 proxy.

When a proxy supports more than one protocol, the selected classification uses this precedence: Socks 5, Socks4, Http connect, Http forward. The scanner no longer labels a proxy as Elite merely because two URLs answered; anonymity remains Unknown unless a dedicated anonymity test is added.

## Architecture

- core/config.py - centralized paths, URLs, limits, and environment overrides.
- core/models.py - proxy data model and canonical protocol names.
- engine/scraper.py - bounded, concurrent source collection and validation.
- engine/scanner.py - concurrent protocol detection and optional GeoIP lookup.
- database/db_manager.py - WAL-enabled SQLite storage with busy timeout and cooldown queries.
- ui/cli.py - Rich terminal dashboard, reports, rechecking, and exports.
- tests/ - deterministic tests for parsing, classification, and database counters.

## Installation and usage

Install Python 3.8 or newer, then run:

    pip install -r requirements.txt
    python main.py

The application creates data and exports directories automatically. GeoIP fields remain Unknown unless a compatible GeoLite2-City database is placed at data/GeoLite2-City.mmdb or PROXIFY_GEO_DB_PATH is set.

## Configuration

The following environment variables can be used without changing source code:

- PROXIFY_MAX_CONCURRENT_TASKS
- PROXIFY_REQUEST_TIMEOUT
- PROXIFY_SCAN_RETRIES
- PROXIFY_RETRY_BACKOFF_SECONDS
- PROXIFY_SQLITE_BUSY_TIMEOUT_MS
- PROXIFY_DB_PATH
- PROXIFY_GEO_DB_PATH
- PROXIFY_LOG_LEVEL

Run the test suite with:

    pytest -q

## Disclaimer

This tool is intended for educational and research use with public proxy sources. Respect the terms of service and applicable laws of every destination and source you access.

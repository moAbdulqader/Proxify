# Proxify

Asynchronous proxy discovery, validation, classification, and SQLite archiving for public proxy research.

Proxify collects proxy endpoints from configured public sources, normalizes and deduplicates them, tests their supported protocols concurrently, classifies working proxies, and stores both active and dead results in a local SQLite database. It is designed as a transparent command-line tool that can be inspected, configured, tested, and extended.

## Features

- Asynchronous collection from multiple public proxy sources.
- Input normalization, IPv4 validation, port-range validation, and deduplication.
- Concurrent protocol detection with configurable timeouts and retries.
- SQLite persistence for active proxies, dead proxies, historical checks, and statistics.
- WAL mode, busy-timeout handling, upserts, and cooldown-aware rescanning.
- Rich terminal dashboard with progress reporting and operational statistics.
- Filtering and export of active proxies by detected protocol or anonymity value.
- Optional GeoIP city lookup through a local GeoLite2 database.
- Configurable DNS resolver for restricted, mobile, or unreliable network environments.
- Graceful interruption during scans and clean resource shutdown.
- Deterministic tests for scraping, classification, and database counters.

## Supported proxy classifications

Every candidate is tested independently against the supported protocol probes:

| Classification | Description |
| --- | --- |
| `Http forward` | HTTP requests sent through an HTTP proxy. |
| `Http connect` | HTTPS tunneling through an HTTP proxy using `CONNECT`. |
| `Socks4` | HTTPS requests routed through a SOCKS4 proxy. |
| `Socks 5` | HTTPS requests routed through a SOCKS5 proxy. |

If a proxy responds successfully through more than one protocol, the stored classification uses this deterministic precedence:

```text
Socks 5 > Socks4 > Http connect > Http forward
```

The scanner does not infer anonymity from the number of successful probes. Anonymity remains `Unknown` unless a dedicated anonymity test provides stronger evidence.

## How the scan works

```text
Configured sources
        |
        v
Normalize -> validate -> deduplicate
        |
        v
Concurrent protocol probes with retries
        |
        v
Select the highest-priority successful protocol
        |
        v
Persist active or dead result in SQLite
```

Each protocol probe uses a configurable test URL and request timeout. A failed probe can be retried with exponential backoff according to the configured scan settings. Results are stored even when a proxy is no longer working, which keeps the database useful for historical statistics and controlled rescans.

## Architecture

| Component | Responsibility |
| --- | --- |
| `core/config.py` | Central configuration, paths, source URLs, limits, DNS, and environment overrides. |
| `core/models.py` | Proxy data model and canonical protocol names. |
| `engine/scraper.py` | Concurrent source retrieval, content limits, parsing, validation, and deduplication. |
| `engine/scanner.py` | Protocol probes, retry handling, deterministic classification, response timing, and optional GeoIP lookup. |
| `database/db_manager.py` | SQLite initialization, WAL configuration, upserts, status tracking, cooldown queries, and statistics. |
| `ui/cli.py` | Rich dashboard, scan controls, rescans, category views, reports, and exports. |
| `tests/` | Automated tests for parsing, protocol selection, database state, and counters. |

## Requirements

- Python 3.8 or newer
- Network access to the configured proxy sources and test endpoints
- A platform capable of installing the packages in `requirements.txt`

The project uses `aiohttp` for asynchronous HTTP operations, `aiohttp-socks` for SOCKS probing, `aiodns` for optional custom DNS resolution, `aiosqlite` for asynchronous SQLite access, and Rich for the terminal interface.

## Installation

```bash
git clone https://github.com/moAbdulqader/Proxify.git
cd Proxify
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Start the interactive terminal application:

```bash
python main.py
```

The main menu provides:

1. Scrape sources and classify new proxies.
2. Recheck active proxies.
3. View active proxies by protocol and anonymity value.
4. View detailed totals, active/dead counts, success rate, and latency.
5. View country statistics when GeoIP data is available.
6. Export active proxies by protocol, anonymity, or as one combined list.
7. Purge the database after an explicit confirmation.
8. Exit cleanly.

Press `Ctrl+C` during a scan to request a safe stop. Completed database writes remain available after interruption.

## Configuration

All settings can be overridden with environment variables without editing source code:

| Variable | Purpose | Default |
| --- | --- | --- |
| `PROXIFY_MAX_CONCURRENT_TASKS` | Maximum concurrent scan tasks. | `100` |
| `PROXIFY_REQUEST_TIMEOUT` | Total timeout for source and proxy requests, in seconds. | `10.0` |
| `PROXIFY_MAX_DOWNLOAD_SIZE` | Maximum source response size, in bytes. | `5242880` |
| `PROXIFY_SCAN_RETRIES` | Number of retries after a failed probe. | `1` |
| `PROXIFY_RETRY_BACKOFF_SECONDS` | Initial retry backoff, in seconds. | `0.5` |
| `PROXIFY_SQLITE_BUSY_TIMEOUT_MS` | SQLite busy timeout, in milliseconds. | `15000` |
| `PROXIFY_DB_PATH` | SQLite database path. | `data/proxy_archive.db` |
| `PROXIFY_GEO_DB_PATH` | GeoLite2-City database path. | `data/GeoLite2-City.mmdb` |
| `PROXIFY_LOG_PATH` | Application log path. | `proxy_master.log` |
| `PROXIFY_LOG_LEVEL` | Python logging level. | `ERROR` |
| `PROXIFY_DNS_SERVERS` | Comma-separated DNS server list. | `1.1.1.1,8.8.8.8` |
| `PROXIFY_HTTP_FORWARD_TEST_URL` | Test URL for HTTP forward probes. | `http://api.ipify.org?format=json` |
| `PROXIFY_HTTP_CONNECT_TEST_URL` | Test URL for HTTP CONNECT probes. | `https://api.ipify.org?format=json` |
| `PROXIFY_SOCKS_TEST_URL` | Test URL for SOCKS4 and SOCKS5 probes. | `https://api.ipify.org?format=json` |

Example:

```bash
PROXIFY_MAX_CONCURRENT_TASKS=120 PROXIFY_REQUEST_TIMEOUT=8 python main.py
```

The application creates the data and exports directories automatically. If the configured DNS servers are unreachable, Proxify logs the source failures and reports the network or DNS problem in the terminal.

## GeoIP support

GeoIP fields remain `Unknown` unless a compatible GeoLite2-City database is available at `data/GeoLite2-City.mmdb` or at the path specified by `PROXIFY_GEO_DB_PATH`. GeoIP enrichment is optional and is not required for proxy discovery or protocol classification.

## Testing

Run the test suite from the repository root:

```bash
pytest -q
```

The repository includes `pytest.ini` and an explicit `core/__init__.py` so the tests work consistently in standard Python environments and Termux.

## Data and generated files

- SQLite data is stored under `data/` by default.
- Exported proxy lists are written under `exports/`.
- Runtime logs are written to `proxy_master.log` by default.
- These generated files should not be committed to source control.

## Responsible use

Proxify is intended for educational, defensive, and research use with publicly available proxy sources. Only access destinations and sources you are authorized to use. Respect applicable laws, terms of service, rate limits, and network policies. The project does not guarantee that a public proxy is safe, anonymous, stable, or suitable for sensitive traffic.

## License

No license file is currently included in the repository. Until a license is added, all rights remain with the repository owner.

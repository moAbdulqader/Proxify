import logging
import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: str):
    value = os.getenv(name, default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    EXPORT_DIR = BASE_DIR / "exports"
    DB_PATH = Path(os.getenv("PROXIFY_DB_PATH", str(DATA_DIR / "proxy_archive.db")))
    GEO_DB_PATH = Path(os.getenv("PROXIFY_GEO_DB_PATH", str(DATA_DIR / "GeoLite2-City.mmdb")))
    LOG_PATH = Path(os.getenv("PROXIFY_LOG_PATH", str(BASE_DIR / "proxy_master.log")))

    MAX_CONCURRENT_TASKS = max(1, _env_int("PROXIFY_MAX_CONCURRENT_TASKS", 100))
    REQUEST_TIMEOUT = max(1.0, _env_float("PROXIFY_REQUEST_TIMEOUT", 10.0))
    MAX_DOWNLOAD_SIZE = max(1024, _env_int("PROXIFY_MAX_DOWNLOAD_SIZE", 5 * 1024 * 1024))
    SCAN_RETRIES = max(0, _env_int("PROXIFY_SCAN_RETRIES", 1))
    RETRY_BACKOFF_SECONDS = max(0.0, _env_float("PROXIFY_RETRY_BACKOFF_SECONDS", 0.5))
    SQLITE_BUSY_TIMEOUT_MS = max(1000, _env_int("PROXIFY_SQLITE_BUSY_TIMEOUT_MS", 15000))
    DNS_SERVERS = _env_list("PROXIFY_DNS_SERVERS", "1.1.1.1,8.8.8.8")

    HTTP_FORWARD_TEST_URL = os.getenv("PROXIFY_HTTP_FORWARD_TEST_URL", "http://api.ipify.org?format=json")
    HTTP_CONNECT_TEST_URL = os.getenv("PROXIFY_HTTP_CONNECT_TEST_URL", "https://api.ipify.org?format=json")
    SOCKS_TEST_URL = os.getenv("PROXIFY_SOCKS_TEST_URL", "https://api.ipify.org?format=json")

    PROXY_SOURCES = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    ]


for directory in (Config.DATA_DIR, Config.EXPORT_DIR, Config.DB_PATH.parent, Config.LOG_PATH.parent):
    directory.mkdir(parents=True, exist_ok=True)

_log_level = getattr(logging, os.getenv("PROXIFY_LOG_LEVEL", "ERROR").upper(), logging.ERROR)
logging.basicConfig(
    filename=Config.LOG_PATH,
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

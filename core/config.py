import os
import logging
from pathlib import Path

class Config:
    # Dynamic Paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    EXPORT_DIR = BASE_DIR / "exports"
    DB_PATH = DATA_DIR / "proxy_archive.db"
    GEO_DB_PATH = DATA_DIR / "GeoLite2-City.mmdb"
    LOG_PATH = BASE_DIR / "proxy_master.log"
    
    # Performance Tuning
    MAX_CONCURRENT_TASKS = 200  
    REQUEST_TIMEOUT = 10        
    MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024  # 5 MB limit for scraping raw proxy lists
    
    # Scraping Sources
    PROXY_SOURCES = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"
    ]

# Initialize Directories
for directory in [Config.DATA_DIR, Config.EXPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Centralized Logging Setup (File based to protect CLI UI)
logging.basicConfig(
    filename=Config.LOG_PATH,
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
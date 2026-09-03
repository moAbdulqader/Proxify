
# 🛡️ Proxify - Advanced Proxy Engine

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Asyncio](https://img.shields.io/badge/asyncio-enabled-success.svg)
![SQLite](https://img.shields.io/badge/database-SQLite-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Proxify** is an elite, fully asynchronous proxy scraper, validator, and manager. Built with a strict modular architecture, it efficiently scrapes thousands of free public proxies, validates them concurrently using `aiohttp`, and archives the working ones in a local SQLite database for quick access, categorization, and exporting.

---

## 🌟 Core Features

* **🚀 Asynchronous Engine:** Utilizes `asyncio` and `aiohttp` to scan hundreds of proxies concurrently without blocking the main thread, ensuring maximum speed and efficiency.
* **🧠 Smart Validation:** Tests proxies against secure HTTPS endpoints to verify response time, protocol (HTTP/HTTPS), and anonymity level (Elite, Anonymous, Transparent).
* **💾 Local Database Caching:** Uses `aiosqlite` to archive working proxies, preventing redundant network requests, avoiding API rate limits, and keeping a historical record of proxy reliability.
* **🌍 Geo-IP Integration:** Resolves proxy locations (Country/City) locally using MaxMind GeoLite2 (if available) for zero-latency lookups.
* **🎨 Rich CLI Dashboard:** A beautiful, interactive terminal user interface built with the `rich` library, providing real-time statistics and progress tracking.
* **📁 Advanced Exporting:** Export active proxies filtered by Protocol (HTTP/HTTPS) or Anonymity Level directly to text files.

---

## 🏗️ Project Architecture

The project follows a strict modular design pattern to ensure scalability and maintainability:

```text
Proxify/
├── core/          # Configuration settings and Data Models (Dataclasses)
├── engine/        # The heavy lifters: Scraper and Async Scanner logic
├── database/      # Asynchronous SQLite database manager
├── ui/            # Interactive CLI controller and dashboard rendering
├── data/          # Local storage for SQLite DB and GeoIP databases
├── exports/       # Output directory for exported proxy lists
└── main.py        # Application entry point
```

---

## 🛠️ Prerequisites

* **Python:** 3.8 or higher
* **Git:** To clone the repository
* **Internet Connection:** Required for scraping and validating proxies

---

## 🚀 Installation & Usage

**1. Clone the repository:**
```bash
git clone https://github.com/moAbdulqader/Proxify.git
cd Proxify
```

**2. Install required dependencies:**
```bash
pip install -r requirements.txt
```

**3. Run the application:**
```bash
python main.py
```

---

## 📊 Proxy Anonymity Levels Explained

Proxify categorizes proxies into three main levels during validation:
* **🟢 Elite (High Anonymity):** The proxy does not send your real IP address and does not identify itself as a proxy. (Best for privacy).
* **🟡 Anonymous:** The proxy does not send your real IP address but identifies itself as a proxy.
* **🔴 Transparent:** The proxy sends your real IP address. (Not recommended for privacy).

---

## ⚠️ Disclaimer

This tool is designed for educational and research purposes only. It fetches data from public, free proxy websites. The developer is not responsible for how these proxies are used or for any misuse of this tool. Always respect the terms of service of the websites you visit.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Mohammed Abdulqader** 
* GitHub: [@moAbdulqader](https://github.com/moAbdulqader)
```

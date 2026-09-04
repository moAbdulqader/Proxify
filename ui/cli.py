import asyncio
from datetime import datetime
from pathlib import Path
from typing import List

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
import pyfiglet

from core.config import Config
from core.models import ProxyType
from database.db_manager import DatabaseManager
from engine.scanner import AdvancedProxyScanner
from engine.scraper import ProxyScraper


class ProxyMasterController:
    def __init__(self, db: DatabaseManager, scraper: ProxyScraper, scanner: AdvancedProxyScanner, stop_event: asyncio.Event):
        self.db = db
        self.scraper = scraper
        self.scanner = scanner
        self.stop_event = stop_event
        self.console = Console()

    def display_banner(self):
        self.console.clear()
        banner = pyfiglet.figlet_format("PROXY MASTER", font="slant")
        self.console.print(f"[cyan]{banner}[/cyan]")
        info = Text()
        info.append("PROXY CLASSIFICATION ENGINE", style="bold magenta")
        info.append(" | ", style="white")
        info.append("Async detection: HTTP forward, HTTP connect, Socks4, Socks 5", style="bold green")
        self.console.print(Panel(info, box=box.DOUBLE_EDGE, border_style="cyan"))

    async def display_dashboard(self):
        stats = await self.db.get_stats()
        layout = Layout()
        layout.split(Layout(name="header", size=3), Layout(name="stats"), Layout(name="main"))
        layout["stats"].split_row(Layout(name="total_stats"), Layout(name="type_stats"))

        totals = Table(show_header=False, box=box.SIMPLE, border_style="blue")
        totals.add_column("Metric", style="cyan")
        totals.add_column("Value", style="yellow")
        totals.add_row("Total in Database", str(stats["total_in_db"]))
        totals.add_row("Active Proxies", str(stats["total_working"]))
        layout["total_stats"].update(Panel(totals, title="Global Statistics"))

        types = Table(show_header=True, box=box.SIMPLE, border_style="green")
        types.add_column("Proxy Type", style="cyan")
        types.add_column("Count", style="yellow", justify="center")
        for proxy_type in ProxyType.ALL:
            types.add_row(proxy_type, str(stats["by_type"].get(proxy_type, 0)))
        layout["type_stats"].update(Panel(types, title="Detected Types"))

        menu = Table(show_header=False, box=box.ROUNDED, border_style="magenta")
        menu.add_column("Key", style="cyan")
        menu.add_column("Action", style="white")
        menu.add_row("[1]", "Scrape and classify new proxies")
        menu.add_row("[2]", "Recheck active proxies")
        menu.add_row("[3]", "View proxies by category")
        menu.add_row("[4]", "Detailed statistics")
        menu.add_row("[5]", "View by country")
        menu.add_row("[6]", "Export active proxies")
        menu.add_row("[7]", "Purge database")
        menu.add_row("[8]", "Exit")
        menu.add_row("[Info]", "Press Ctrl+C during a scan to stop safely")
        layout["main"].update(Panel(menu, title="Control Center", border_style="yellow"))
        self.console.print(layout)

    async def _execute_scan_queue(self, proxies_to_scan: List[str], scan_title: str):
        if not proxies_to_scan:
            return
        semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_TASKS)
        queue = asyncio.Queue()
        for proxy in proxies_to_scan:
            queue.put_nowait(proxy)
        self.stop_event.clear()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            scan_task = progress.add_task(f"[cyan]{scan_title}...", total=len(proxies_to_scan))

            async def worker():
                while not self.stop_event.is_set():
                    try:
                        proxy = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    try:
                        await self.scanner.check_proxy(proxy, semaphore)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self.console.print(f"[red]Scan error for {proxy}: {exc}[/red]")
                    finally:
                        queue.task_done()
                        progress.advance(scan_task)

            workers = [
                asyncio.create_task(worker())
                for _ in range(min(Config.MAX_CONCURRENT_TASKS, len(proxies_to_scan)))
            ]
            try:
                await asyncio.gather(*workers)
            except (KeyboardInterrupt, asyncio.CancelledError):
                self.stop_event.set()
                for task in workers:
                    task.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
                raise

    async def run_auto_mode(self):
        self.console.print("[cyan]Phase 1: Scraping proxy sources...[/cyan]")
        raw_proxies = await self.scraper.scrape_all()
        if not raw_proxies:
            self.console.print("[red]No proxies were retrieved. Check network access and logs.[/red]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return

        self.console.print(f"[green]Retrieved {len(raw_proxies)} unique proxies.[/green]")
        proxies_to_scan = await self.db.filter_proxies_to_scan(raw_proxies)
        self.console.print(f"[yellow]Skipped {len(raw_proxies) - len(proxies_to_scan)} proxies inside cooldown.[/yellow]")
        if not proxies_to_scan:
            self.console.print("[green]All proxies are up to date.[/green]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return

        await self._execute_scan_queue(proxies_to_scan, "Detecting proxy types")
        self.console.print("\n[green]Scan completed.[/green]")
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def rescore_existing(self):
        proxies = await self.db.get_active_proxies()
        if not proxies:
            self.console.print("[yellow]No active proxies found.[/yellow]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return
        await self._execute_scan_queue(proxies, "Rechecking active proxies")
        self.console.print("\n[green]Recheck completed.[/green]")
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def view_by_category(self):
        self.console.clear()
        table = Table(title="Active Proxies by Category", box=box.ROUNDED)
        table.add_column("Proxy Type", style="cyan")
        table.add_column("Anonymity", style="magenta")
        table.add_column("Count", style="yellow", justify="center")
        rows = await self.db.get_category_stats()
        if not rows:
            self.console.print("[yellow]No active proxies available.[/yellow]")
        else:
            for proxy_type, anonymity, count in rows:
                table.add_row(proxy_type, anonymity, str(count))
            self.console.print(table)
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def detailed_statistics(self):
        self.console.clear()
        stats = await self.db.get_detailed_stats()
        table = Table(title="Comprehensive Statistics", box=box.DOUBLE_EDGE)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow", justify="right")
        table.add_row("Total Stored", str(stats["total"]))
        table.add_row("Currently Active", f"[green]{stats['active']}[/green]")
        table.add_row("Currently Dead", f"[red]{stats['dead']}[/red]")
        table.add_row("Historical Check Success Rate", f"{stats['success_rate']:.2f}%")
        table.add_row("Average Active Latency", f"{stats['average_latency']:.2f} ms")
        self.console.print(table)
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def view_by_country(self):
        self.console.clear()
        countries = await self.db.get_country_stats()
        if not countries:
            self.console.print("[yellow]No country data available.[/yellow]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return
        table = Table(title="Top Countries", box=box.SIMPLE)
        table.add_column("Country", style="cyan")
        table.add_column("Count", style="yellow")
        for country, count in countries:
            table.add_row(country, str(count))
        self.console.print(table)
        await asyncio.to_thread(input, "\nPress Enter to return...")

    @staticmethod
    def _write_export(path: Path, proxies: List[str]):
        path.write_text("\n".join(proxies) + ("\n" if proxies else ""), encoding="utf-8")

    async def export_proxies(self):
        self.console.clear()
        menu = Table(title="Export Options", box=box.ROUNDED)
        menu.add_column("Key", style="cyan")
        menu.add_column("Action", style="white")
        menu.add_row("[1]", "Export by detected type")
        menu.add_row("[2]", "Export by anonymity")
        menu.add_row("[3]", "Export all active proxies")
        menu.add_row("[0]", "Back")
        self.console.print(menu)
        choice = (await asyncio.to_thread(input, "\nSelect an option: ")).strip()
        if choice == "0":
            return

        folder = Config.EXPORT_DIR / f"Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if choice == "1":
                for proxy_type in ProxyType.ALL:
                    proxies = await self.db.get_active_by_type(proxy_type)
                    if proxies:
                        self._write_export(folder / f"{proxy_type.replace(' ', '_')}.txt", proxies)
            elif choice == "2":
                for anonymity in ("Elite", "Anonymous", "Transparent", "Unknown"):
                    proxies = await self.db.get_active_by_anonymity(anonymity)
                    if proxies:
                        self._write_export(folder / f"{anonymity}.txt", proxies)
            elif choice == "3":
                self._write_export(folder / "all_active.txt", await self.db.get_active_proxies())
            else:
                self.console.print("[yellow]Invalid option.[/yellow]")
                return
            self.console.print(f"[green]Exported successfully to {folder}[/green]")
        except Exception as exc:
            self.console.print(f"[red]Export error: {exc}[/red]")
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def purge_database(self):
        self.console.print("[bold red]This permanently deletes all proxy history.[/bold red]")
        confirm = await asyncio.to_thread(input, "Type PURGE to confirm: ")
        if confirm.strip() == "PURGE":
            await self.db.purge()
            self.console.print("[green]Database purged.[/green]")
        else:
            self.console.print("[yellow]Purge aborted.[/yellow]")
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def run(self):
        while True:
            self.display_banner()
            await self.display_dashboard()
            choice = (await asyncio.to_thread(input, "\nSelect an action: ")).strip()
            try:
                if choice == "1":
                    await self.run_auto_mode()
                elif choice == "2":
                    await self.rescore_existing()
                elif choice == "3":
                    await self.view_by_category()
                elif choice == "4":
                    await self.detailed_statistics()
                elif choice == "5":
                    await self.view_by_country()
                elif choice == "6":
                    await self.export_proxies()
                elif choice == "7":
                    await self.purge_database()
                elif choice == "8":
                    self.console.print("[green]Goodbye.[/green]")
                    return
                else:
                    self.console.print("[red]Invalid selection.[/red]")
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                self.stop_event.set()

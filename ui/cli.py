import asyncio
import aiosqlite
from datetime import datetime
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.text import Text
from rich import box
import pyfiglet

from core.config import Config
from database.db_manager import DatabaseManager
from engine.scraper import ProxyScraper
from engine.scanner import AdvancedProxyScanner

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
        
        info_text = Text()
        info_text.append("ELITE PROXY SYSTEM V4.1 (REFACTORED)", style="bold magenta")
        info_text.append(" | ", style="white")
        info_text.append("Fully Asynchronous & Modular", style="bold green")
        self.console.print(Panel(info_text, box=box.DOUBLE_EDGE, border_style="cyan"))
        
    async def display_dashboard(self):
        stats = await self.db.get_stats()
        
        layout = Layout()
        layout.split(Layout(name="header", size=3), Layout(name="stats"), Layout(name="main"))
        layout["stats"].split_row(Layout(name="total_stats"), Layout(name="type_stats"))
        
        total_stats = Table(show_header=False, box=box.SIMPLE, border_style="blue")
        total_stats.add_column("Metric", style="cyan")
        total_stats.add_column("Value", style="yellow")
        total_stats.add_row("📊 Total in Database", str(stats['total_in_db']))
        total_stats.add_row("✅ Active Proxies", str(stats['total_working']))
        layout["total_stats"].update(Panel(total_stats, title="📈 Global Statistics"))
        
        type_stats = Table(show_header=True, box=box.SIMPLE, border_style="green")
        type_stats.add_column("Protocol", style="cyan")
        type_stats.add_column("Count", style="yellow", justify="center")
        for p_type, count in stats['by_type'].items():
            type_stats.add_row(p_type, str(count))
        if not stats['by_type']:
            type_stats.add_row("N/A", "0")
        layout["type_stats"].update(Panel(type_stats, title="🔢 Protocol Distribution"))
        
        menu = Table(show_header=False, box=box.ROUNDED, border_style="magenta")
        menu.add_column("Key", style="cyan")
        menu.add_column("Action", style="white")
        menu.add_row("[1]", "Scrape New Proxies & Scan (Auto-Mode)")
        menu.add_row("[2]", "Rescore Existing Database Proxies")
        menu.add_row("[3]", "View Proxies by Category")
        menu.add_row("[4]", "Detailed System Statistics")
        menu.add_row("[5]", "View Proxies by Country")
        menu.add_row("[6]", "Advanced Export Options")
        menu.add_row("[7]", "⚠️ Purge Database (Danger)")
        menu.add_row("[8]", "Exit System")
        menu.add_row("[Info]", "Press Ctrl+C during any scan to safely abort.")
        layout["main"].update(Panel(menu, title="🎮 Control Center", border_style="yellow"))
        
        self.console.print(layout)

    async def _execute_scan_queue(self, proxies_to_scan: List[str], scan_title: str):
        """Execute scanner tasks gracefully with progress tracking."""
        semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_TASKS)
        self.stop_event.clear()
        
        tasks = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            scan_task = progress.add_task(f"[cyan]{scan_title}...", total=len(proxies_to_scan))
            
            for proxy in proxies_to_scan:
                task = asyncio.create_task(self.scanner.check_proxy(proxy, 'HTTP', semaphore))
                task.add_done_callback(lambda _: progress.advance(scan_task))
                tasks.append(task)
                
            try:
                await asyncio.gather(*tasks)
            except KeyboardInterrupt:
                self.console.print("\n[bold yellow]⏹️ Abort signal received (Ctrl+C). Cancelling pending tasks safely...[/bold yellow]")
                self.stop_event.set()
                # Await cancellation to ensure clean state
                await asyncio.gather(*tasks, return_exceptions=True)

    async def run_auto_mode(self):
        self.console.print("[cyan]\n🌐 Phase 1: Scraping Proxies from Sources...[/cyan]")
        raw_proxies = await self.scraper.scrape_all()
        
        if not raw_proxies:
            self.console.print("[red]❌ Failed to retrieve proxies. Check your network or logs.[/red]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return
            
        self.console.print(f"[green]✅ Successfully scraped {len(raw_proxies)} unique proxies.[/green]")
        self.console.print("[cyan]⏳ Phase 2: Applying Smart Cooldown TTL Filter...[/cyan]")
        
        proxies_to_scan = await self.db.filter_proxies_to_scan(raw_proxies)
        skipped = len(raw_proxies) - len(proxies_to_scan)
        
        self.console.print(f"[yellow]⏭️ Skipped {skipped} recently checked proxies to save time.[/yellow]")
        
        if not proxies_to_scan:
            self.console.print("[green]✅ All scraped proxies are already up-to-date![/green]")
            await asyncio.to_thread(input, "\nPress Enter to return to Dashboard...")
            return
            
        self.console.print(f"[cyan]⚡ Phase 3: Asynchronous Deep Scan Initialization ({len(proxies_to_scan)} targets)...[/cyan]")
        await self._execute_scan_queue(proxies_to_scan, "Scanning & Validating")
            
        self.console.print("\n[green]✅ Auto-Mode Completed Successfully![/green]")
        await asyncio.to_thread(input, "\nPress Enter to return to Dashboard...")

    async def rescore_existing(self):
        self.console.print("[cyan]\n🔄 Fetching active proxies from database...[/cyan]")
        
        async with aiosqlite.connect(Config.DB_PATH) as conn:
            async with conn.execute("SELECT proxy FROM proxy_archive WHERE status='active'") as cursor:
                rows = await cursor.fetchall()
                proxies_to_scan = [row[0] for row in rows]
            
        if not proxies_to_scan:
            self.console.print("[yellow]⚠️ No active proxies found in the database to rescore.[/yellow]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return
            
        self.console.print(f"[cyan]⚡ Rescoring {len(proxies_to_scan)} active proxies...[/cyan]")
        await self._execute_scan_queue(proxies_to_scan, "Rescoring Proxies")
        
        self.console.print("\n[green]✅ Rescoring Completed Successfully![/green]")
        await asyncio.to_thread(input, "\nPress Enter to return to Dashboard...")

    async def view_by_category(self):
        self.console.clear()
        table = Table(title="📋 Active Proxies by Category", box=box.ROUNDED)
        table.add_column("Protocol", style="cyan", justify="center")
        table.add_column("Anonymity Level", style="magenta", justify="center")
        table.add_column("Active Count", style="yellow", justify="center")
        
        async with aiosqlite.connect(Config.DB_PATH) as conn:
            async with conn.execute('''
                SELECT proxy_type, anonymity_level, COUNT(*) 
                FROM proxy_archive 
                WHERE status='active' 
                GROUP BY proxy_type, anonymity_level 
                ORDER BY proxy_type, anonymity_level
            ''') as cursor:
                rows = await cursor.fetchall()
            
        if not rows:
            self.console.print("[yellow]⚠️ No active proxies available.[/yellow]")
        else:
            for p_type, anon, count in rows:
                table.add_row(p_type, anon, str(count))
            self.console.print(table)
            
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def detailed_statistics(self):
        self.console.clear()
        async with aiosqlite.connect(Config.DB_PATH) as conn:
            async with conn.execute("SELECT COUNT(*) FROM proxy_archive") as cur:
                total = (await cur.fetchone())[0]
            async with conn.execute("SELECT COUNT(*) FROM proxy_archive WHERE status='active'") as cur:
                active = (await cur.fetchone())[0]
            async with conn.execute("SELECT COUNT(*) FROM proxy_archive WHERE status='dead'") as cur:
                dead = (await cur.fetchone())[0]
            async with conn.execute("SELECT AVG(response_time) FROM proxy_archive WHERE status='active' AND response_time > 0") as cur:
                avg_latency = (await cur.fetchone())[0] or 0.0
            
        success_rate = (active / total * 100) if total > 0 else 0.0
        
        stats_table = Table(title="📊 Comprehensive System Statistics", box=box.DOUBLE_EDGE)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="yellow", justify="right")
        
        stats_table.add_row("Total Proxies Stored", str(total))
        stats_table.add_row("Currently Active", f"[green]{active}[/green]")
        stats_table.add_row("Currently Dead", f"[red]{dead}[/red]")
        stats_table.add_row("Global Success Rate", f"{success_rate:.2f}%")
        stats_table.add_row("Average Latency", f"{avg_latency:.2f} ms")
        
        self.console.print(stats_table)
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def view_by_country(self):
        self.console.clear()
        async with aiosqlite.connect(Config.DB_PATH) as conn:
            async with conn.execute('''
                SELECT country, COUNT(*) 
                FROM proxy_archive 
                WHERE status='active' AND country != 'Unknown' 
                GROUP BY country 
                ORDER BY COUNT(*) DESC LIMIT 15
            ''') as cursor:
                countries = await cursor.fetchall()
            
        if not countries:
            self.console.print("[yellow]⚠️ No country data available for active proxies.[/yellow]")
            await asyncio.to_thread(input, "\nPress Enter to return...")
            return
            
        country_table = Table(title="🌍 Top 15 Countries (Active Proxies)", box=box.SIMPLE)
        country_table.add_column("Country", style="cyan")
        country_table.add_column("Count", style="green", justify="right")
        
        for country, count in countries:
            country_table.add_row(country, str(count))
            
        self.console.print(country_table)
        
        target = await asyncio.to_thread(input, "\n[bold cyan]Enter Country Name to view proxies (or press Enter to cancel): [/bold cyan]")
        target = target.strip()
        
        if not target:
            return
            
        async with aiosqlite.connect(Config.DB_PATH) as conn:
            async with conn.execute('''
                SELECT proxy, proxy_type, anonymity_level, response_time 
                FROM proxy_archive 
                WHERE status='active' AND country LIKE ? 
                ORDER BY response_time ASC LIMIT 30
            ''', (f"%{target}%",)) as cursor:
                proxies = await cursor.fetchall()
            
        if not proxies:
            self.console.print(f"[red]❌ No active proxies found for '{target}'.[/red]")
        else:
            p_table = Table(title=f"🚀 Top 30 Fastest Proxies in {target}", box=box.ROUNDED)
            p_table.add_column("Proxy", style="cyan")
            p_table.add_column("Protocol", style="magenta")
            p_table.add_column("Anonymity", style="yellow")
            p_table.add_column("Latency (ms)", style="green", justify="right")
            
            for proxy, p_type, anon, resp in proxies:
                p_table.add_row(proxy, p_type, anon, f"{resp:.2f}")
                
            self.console.print(p_table)
            
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def export_proxies(self):
        self.console.clear()
        menu = Table(title="📁 Advanced Export Options", box=box.ROUNDED)
        menu.add_column("Key", style="cyan")
        menu.add_column("Option", style="yellow")
        menu.add_row("[1]", "Export by Protocol (HTTP/HTTPS)")
        menu.add_row("[2]", "Export by Anonymity Level")
        menu.add_row("[3]", "Export All Active Proxies (Raw TXT)")
        menu.add_row("[0]", "Back to Dashboard")
        self.console.print(menu)
        
        choice = await asyncio.to_thread(input, "\n[bold cyan]Select an option: [/bold cyan]")
        choice = choice.strip()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = Config.EXPORT_DIR / f"Export_{timestamp}"
        
        try:
            async with aiosqlite.connect(Config.DB_PATH) as conn:
                if choice == '1':
                    export_folder.mkdir(exist_ok=True)
                    for proto in ['HTTP', 'HTTPS']:
                        async with conn.execute("SELECT proxy FROM proxy_archive WHERE proxy_type=? AND status='active'", (proto,)) as cursor:
                            proxies = await cursor.fetchall()
                        if proxies:
                            with open(export_folder / f"{proto}.txt", 'w') as f:
                                f.write('\n'.join([p[0] for p in proxies]))
                    self.console.print(f"[green]✅ Exported successfully to {export_folder}[/green]")
                    
                elif choice == '2':
                    export_folder.mkdir(exist_ok=True)
                    for anon in ['Elite', 'Anonymous', 'Transparent']:
                        async with conn.execute("SELECT proxy FROM proxy_archive WHERE anonymity_level=? AND status='active'", (anon,)) as cursor:
                            proxies = await cursor.fetchall()
                        if proxies:
                            with open(export_folder / f"{anon}.txt", 'w') as f:
                                f.write('\n'.join([p[0] for p in proxies]))
                    self.console.print(f"[green]✅ Exported successfully to {export_folder}[/green]")
                    
                elif choice == '3':
                    export_folder.mkdir(exist_ok=True)
                    async with conn.execute("SELECT proxy FROM proxy_archive WHERE status='active'") as cursor:
                        proxies = await cursor.fetchall()
                    with open(export_folder / "all_active.txt", 'w') as f:
                        f.write('\n'.join([p[0] for p in proxies]))
                    self.console.print(f"[green]✅ Exported {len(proxies)} proxies to {export_folder}[/green]")
                    
        except Exception as e:
            self.console.print(f"[red]Export Error: {e}[/red]")
            
        if choice != '0':
            await asyncio.to_thread(input, "\nPress Enter to return...")

    async def purge_database(self):
        self.console.print("\n[bold red]════════════════════════════════════════════[/bold red]")
        self.console.print("[bold red]⚠️  WARNING: THIS ACTION IS IRREVERSIBLE![/bold red]")
        self.console.print("[yellow]This will permanently delete all scanned proxies and history.[/yellow]")
        self.console.print("[bold red]════════════════════════════════════════════[/bold red]")
        
        confirm = await asyncio.to_thread(input, "\n[bold red]Type 'PURGE' to confirm: [/bold red]")
        
        if confirm.strip() == 'PURGE':
            async with aiosqlite.connect(Config.DB_PATH) as conn:
                await conn.execute("DELETE FROM proxy_archive")
                await conn.commit()
            self.console.print("[green]✅ Database successfully purged.[/green]")
        else:
            self.console.print("[yellow]Purge aborted.[/yellow]")
            
        await asyncio.to_thread(input, "\nPress Enter to return...")

    async def run(self):
        while True:
            self.display_banner()
            await self.display_dashboard()
            
            choice = await asyncio.to_thread(input, "\n[bold cyan]🔹 Select an action: [/bold cyan]")
            choice = choice.strip()
            
            try:
                if choice == '1':
                    await self.run_auto_mode()
                elif choice == '2':
                    await self.rescore_existing()
                elif choice == '3':
                    await self.view_by_category()
                elif choice == '4':
                    await self.detailed_statistics()
                elif choice == '5':
                    await self.view_by_country()
                elif choice == '6':
                    await self.export_proxies()
                elif choice == '7':
                    await self.purge_database()
                elif choice == '8':
                    self.console.print("[green]👋 Shutting down Proxy Master. Goodbye![/green]")
                    break
                else:
                    self.console.print("[red]❌ Invalid selection.[/red]")
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                # Top level interrupt handling if not inside a scan
                pass
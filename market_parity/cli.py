"""Command-line interface with rich visual feedback for Market Parity Checker."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .apify_trigger import ApifyTriggerClient
from .crawler import MarketplaceCrawler
from .database import DuckDBMarketStore
from .models import MarketplaceSource
from .parity_checker import ParityChecker

console = Console()


def run_pipeline(
    query: str,
    source: MarketplaceSource,
    db_path: Optional[str] = None,
    dry_run: bool = False,
    scenario: Optional[str] = None,
    apify_actor: str = "apify/web-scraper",
) -> int:
    """Execute complete autonomous loop: Crawl -> Parity Check -> Trigger -> Commit."""
    console.print(
        Panel.fit(
            f"[bold cyan]Autonomous Market Scraping & Fast Parity Check[/bold cyan]\n"
            f"[dim]Query:[/dim] [yellow]{query}[/yellow] | [dim]Source:[/dim] [green]{source.value.upper()}[/green] | [dim]Dry Run:[/dim] {dry_run}",
            border_style="cyan",
        )
    )

    store = DuckDBMarketStore(db_path=db_path)
    crawler = MarketplaceCrawler()
    checker = ParityChecker(store)
    apify = ApifyTriggerClient()

    # 1. Fast Crawl
    with console.status(f"[bold green]Crawling {source.value} index..."):
        fresh = crawler.fetch_listings(query=query, source=source, simulated_scenario=scenario)

    console.print(f"✓ Crawled [bold]{len(fresh)}[/bold] candidate listing(s) from {source.value}.")

    # 2. Local Parity Check
    with console.status("[bold blue]Running DuckDB parity comparison..."):
        delta = checker.evaluate_parity(query=query, marketplace=source, fresh_listings=fresh)

    # 3. Print Results Table
    table = Table(title=f"Parity Delta Analysis ({query})", border_style="blue")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="bold")
    table.add_column("Details", style="dim")

    table.add_row("Scanned Listings", str(delta.total_scanned), "Total indexed items")
    table.add_row(
        "New Listings",
        f"[green]{len(delta.new_listings)}[/green]",
        f"e.g. {delta.new_listings[0].title[:35]}..." if delta.new_listings else "None",
    )
    table.add_row(
        "Price Drops",
        f"[yellow]{len(delta.price_drops)}[/yellow]",
        f"Drop: €{delta.price_drops[0][1]} -> €{delta.price_drops[0][0].price}" if delta.price_drops else "None",
    )
    table.add_row("Unchanged in Parity", f"[dim]{delta.unchanged_count}[/dim]", "Identical hash matched in DuckDB")
    console.print(table)

    # Decision Banner
    if delta.should_trigger_deep_scrape:
        console.print(
            Panel(
                f"[bold red]⚡ Actionable Disparity Detected[/bold red]\n{delta.rationale}",
                border_style="red",
            )
        )
        # 4. Trigger Apify Actor conditionally
        trigger_res = apify.trigger_actor(actor_id=apify_actor, delta=delta, dry_run=dry_run)
        console.print(f"[bold magenta]Apify Result:[/bold magenta] {trigger_res.get('status').upper()} - {trigger_res}")
    else:
        console.print(
            Panel(
                f"[bold green]✓ In Parity with Local Cache[/bold green]\n{delta.rationale}\n[bold yellow]Cost Saved:[/bold yellow] Downstream Apify cloud actor execution bypassed.",
                border_style="green",
            )
        )

    # 5. Commit state to DuckDB unless dry run
    if not dry_run:
        checker.commit_delta(fresh, delta)
        console.print("✓ Fresh state synchronized with DuckDB.")
    else:
        console.print("[dim][DRY-RUN] DuckDB updates skipped.[/dim]")

    store.close()
    return 0


def show_stats(db_path: Optional[str] = None) -> int:
    """Display analytics and cloud cost savings."""
    store = DuckDBMarketStore(db_path=db_path)
    stats = store.get_stats()
    store.close()

    table = Table(title="DuckDB Market Parity Metrics & Cost Savings", border_style="green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold yellow")

    table.add_row("Total Tracked Listings", str(stats["total_tracked_listings"]))
    table.add_row("Total Parity Runs", str(stats["total_parity_runs"]))
    table.add_row("Cloud Deep Scrapes Triggered", str(stats["deep_scrapes_triggered"]))
    table.add_row("Cloud Scrapes Avoided (Savings)", f"[bold green]{stats['cloud_runs_saved']}[/bold green]")
    table.add_row("Cloud Cost Efficiency", f"[bold green]{stats['savings_efficiency_pct']}%[/bold green]")

    console.print(table)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Market Scraping & Fast Parity Check CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run-pipeline
    p_run = subparsers.add_parser("run", help="Run full pipeline: crawl -> check parity -> trigger -> commit")
    p_run.add_argument("--query", "-q", default="thinkpad x1", help="Search query keyword")
    p_run.add_argument(
        "--source", "-s", default="mock", choices=["mock", "ebay", "marktplaats"], help="Marketplace to crawl"
    )
    p_run.add_argument("--db-path", default=None, help="Custom DuckDB file path")
    p_run.add_argument("--dry-run", action="store_true", help="Preview without writing to DuckDB or triggering cloud")
    p_run.add_argument(
        "--scenario", choices=["baseline", "price_drop", "new_items", "unchanged"], default=None, help="Mock scenario"
    )

    # stats
    p_stats = subparsers.add_parser("stats", help="Show DuckDB analytical metrics and cloud savings")
    p_stats.add_argument("--db-path", default=None, help="Custom DuckDB file path")

    args = parser.parse_args()

    if args.command == "run":
        return run_pipeline(
            query=args.query,
            source=MarketplaceSource(args.source),
            db_path=args.db_path,
            dry_run=args.dry_run,
            scenario=args.scenario,
        )
    elif args.command == "stats":
        return show_stats(db_path=args.db_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())

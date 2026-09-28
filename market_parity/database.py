"""DuckDB local persistence and high-speed analytical store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from .models import ListingItem, ListingStatus, MarketplaceSource

logger = logging.getLogger("market_parity.database")


class DuckDBMarketStore:
    """Embedded analytical database for lightning-fast marketplace parity matching."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = str(Path("data/market_parity.duckdb").absolute())
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_path = str(db_path)

        if self.db_path != ":memory:" and Path(self.db_path).exists() and Path(self.db_path).stat().st_size == 0:
            Path(self.db_path).unlink()

        self._conn = duckdb.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create analytical tables if not present."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_listings (
                external_id VARCHAR NOT NULL,
                marketplace VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                price DOUBLE NOT NULL,
                currency VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                seller VARCHAR,
                location VARCHAR,
                content_hash VARCHAR NOT NULL,
                first_seen_at TIMESTAMP NOT NULL,
                last_seen_at TIMESTAMP NOT NULL,
                status VARCHAR NOT NULL,
                PRIMARY KEY (marketplace, external_id)
            );
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                external_id VARCHAR NOT NULL,
                marketplace VARCHAR NOT NULL,
                price DOUBLE NOT NULL,
                currency VARCHAR NOT NULL,
                recorded_at TIMESTAMP NOT NULL
            );
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parity_audit_logs (
                run_id VARCHAR PRIMARY KEY,
                query VARCHAR NOT NULL,
                marketplace VARCHAR NOT NULL,
                total_scanned INTEGER NOT NULL,
                new_count INTEGER NOT NULL,
                price_drop_count INTEGER NOT NULL,
                unchanged_count INTEGER NOT NULL,
                triggered_deep_scrape BOOLEAN NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
            """
        )

    def get_listing(self, marketplace: MarketplaceSource, external_id: str) -> Optional[ListingItem]:
        """Fetch single listing by key."""
        res = self._conn.execute(
            """
            SELECT external_id, marketplace, title, price, currency, url,
                   seller, location, content_hash, first_seen_at, last_seen_at, status
            FROM market_listings
            WHERE marketplace = ? AND external_id = ?
            """,
            [marketplace.value, external_id],
        ).fetchone()

        if not res:
            return None

        return ListingItem(
            external_id=res[0],
            marketplace=MarketplaceSource(res[1]),
            title=res[2],
            price=float(res[3]),
            currency=res[4],
            url=res[5],
            seller=res[6],
            location=res[7],
            content_hash=res[8],
            first_seen_at=res[9],
            last_seen_at=res[10],
            status=ListingStatus(res[11]),
        )

    def get_known_listings_map(self, marketplace: MarketplaceSource) -> Dict[str, ListingItem]:
        """Load all active listings for a marketplace into an in-memory dictionary for sub-millisecond lookups."""
        rows = self._conn.execute(
            """
            SELECT external_id, marketplace, title, price, currency, url,
                   seller, location, content_hash, first_seen_at, last_seen_at, status
            FROM market_listings
            WHERE marketplace = ?
            """,
            [marketplace.value],
        ).fetchall()

        result: Dict[str, ListingItem] = {}
        for r in rows:
            item = ListingItem(
                external_id=r[0],
                marketplace=MarketplaceSource(r[1]),
                title=r[2],
                price=float(r[3]),
                currency=r[4],
                url=r[5],
                seller=r[6],
                location=r[7],
                content_hash=r[8],
                first_seen_at=r[9],
                last_seen_at=r[10],
                status=ListingStatus(r[11]),
            )
            result[item.external_id] = item
        return result

    def upsert_listing(self, item: ListingItem) -> bool:
        """Upsert a listing and record price history if price shifted."""
        existing = self.get_listing(item.marketplace, item.external_id)
        now = datetime.now(timezone.utc)

        if existing is None:
            # Insert brand new listing
            self._conn.execute(
                """
                INSERT INTO market_listings (
                    external_id, marketplace, title, price, currency, url,
                    seller, location, content_hash, first_seen_at, last_seen_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    item.external_id,
                    item.marketplace.value,
                    item.title,
                    item.price,
                    item.currency,
                    item.url,
                    item.seller,
                    item.location,
                    item.content_hash,
                    now,
                    now,
                    item.status.value,
                ],
            )
            self._conn.execute(
                """
                INSERT INTO price_history (external_id, marketplace, price, currency, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [item.external_id, item.marketplace.value, item.price, item.currency, now],
            )
            return True
        else:
            # Update existing
            price_changed = abs(existing.price - item.price) > 0.001
            self._conn.execute(
                """
                UPDATE market_listings
                SET title = ?, price = ?, currency = ?, url = ?, seller = ?,
                    location = ?, content_hash = ?, last_seen_at = ?, status = ?
                WHERE marketplace = ? AND external_id = ?
                """,
                [
                    item.title,
                    item.price,
                    item.currency,
                    item.url,
                    item.seller,
                    item.location,
                    item.content_hash,
                    now,
                    item.status.value,
                    item.marketplace.value,
                    item.external_id,
                ],
            )
            if price_changed:
                self._conn.execute(
                    """
                    INSERT INTO price_history (external_id, marketplace, price, currency, recorded_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [item.external_id, item.marketplace.value, item.price, item.currency, now],
                )
            return False

    def log_parity_run(
        self,
        run_id: str,
        query: str,
        marketplace: MarketplaceSource,
        total_scanned: int,
        new_count: int,
        price_drop_count: int,
        unchanged_count: int,
        triggered_deep_scrape: bool,
    ) -> None:
        """Persist audit execution metric."""
        self._conn.execute(
            """
            INSERT INTO parity_audit_logs (
                run_id, query, marketplace, total_scanned, new_count,
                price_drop_count, unchanged_count, triggered_deep_scrape, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                query,
                marketplace.value,
                total_scanned,
                new_count,
                price_drop_count,
                unchanged_count,
                triggered_deep_scrape,
                datetime.now(timezone.utc),
            ],
        )

    def get_stats(self) -> Dict[str, Any]:
        """Compute aggregate database statistics."""
        total_listings = self._conn.execute("SELECT count(*) FROM market_listings").fetchone()[0]
        total_runs = self._conn.execute("SELECT count(*) FROM parity_audit_logs").fetchone()[0]
        deep_scrapes_triggered = self._conn.execute(
            "SELECT count(*) FROM parity_audit_logs WHERE triggered_deep_scrape = true"
        ).fetchone()[0]

        marketplaces = self._conn.execute(
            "SELECT marketplace, count(*) FROM market_listings GROUP BY marketplace"
        ).fetchall()

        cost_saved_runs = total_runs - deep_scrapes_triggered
        cost_savings_pct = (cost_saved_runs / total_runs * 100) if total_runs > 0 else 0.0

        return {
            "total_tracked_listings": total_listings,
            "total_parity_runs": total_runs,
            "deep_scrapes_triggered": deep_scrapes_triggered,
            "cloud_runs_saved": cost_saved_runs,
            "savings_efficiency_pct": round(cost_savings_pct, 1),
            "marketplace_counts": dict(marketplaces),
        }

    def close(self) -> None:
        """Safely close connection."""
        self._conn.close()

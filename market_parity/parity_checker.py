"""High-speed parity detection engine comparing scraped listings with DuckDB state."""

from __future__ import annotations

import logging
import uuid
from typing import List

from .database import DuckDBMarketStore
from .models import ListingItem, ListingStatus, MarketplaceSource, ParityDelta

logger = logging.getLogger("market_parity.parity_checker")


class ParityChecker:
    """Computes exact delta between new scrape and known listings in DuckDB."""

    def __init__(self, store: DuckDBMarketStore):
        self.store = store

    def evaluate_parity(
        self,
        query: str,
        marketplace: MarketplaceSource,
        fresh_listings: List[ListingItem],
        price_drop_threshold_pct: float = 0.0,
    ) -> ParityDelta:
        """Analyze listings against DuckDB state to determine if deep scraping is necessary."""
        known_map = self.store.get_known_listings_map(marketplace)

        new_items: List[ListingItem] = []
        price_drops: List[tuple[ListingItem, float]] = []
        price_increases: List[tuple[ListingItem, float]] = []
        unchanged_count = 0

        for fresh in fresh_listings:
            existing = known_map.get(fresh.external_id)

            if existing is None:
                # 1. Brand new listing never seen before
                fresh.status = ListingStatus.ACTIVE
                new_items.append(fresh)
            elif fresh.content_hash == existing.content_hash:
                # 2. Perfect hash parity (price & title unchanged)
                unchanged_count += 1
            elif fresh.price < existing.price:
                # 3. Price drop detected
                drop_amount = existing.price - fresh.price
                drop_pct = (drop_amount / existing.price) * 100.0 if existing.price > 0 else 0.0
                if drop_pct >= price_drop_threshold_pct:
                    fresh.status = ListingStatus.PRICE_DROPPED
                    price_drops.append((fresh, existing.price))
                else:
                    unchanged_count += 1
            elif fresh.price > existing.price:
                # 4. Price increased
                fresh.status = ListingStatus.PRICE_INCREASED
                price_increases.append((fresh, existing.price))
            else:
                unchanged_count += 1

        # Decision policy: Trigger deep scraping only if actionable delta exists
        should_trigger = bool(new_items or price_drops)
        if should_trigger:
            reasons = []
            if new_items:
                reasons.append(f"{len(new_items)} new listing(s)")
            if price_drops:
                reasons.append(f"{len(price_drops)} price drop(s)")
            rationale = "Parity disparity detected: " + ", ".join(reasons) + ". Triggering deep scraper."
        else:
            rationale = f"All {unchanged_count} listings in parity with local database. Downstream cloud scrape bypassed."

        delta = ParityDelta(
            query=query,
            marketplace=marketplace,
            total_scanned=len(fresh_listings),
            new_listings=new_items,
            price_drops=price_drops,
            price_increases=price_increases,
            unchanged_count=unchanged_count,
            should_trigger_deep_scrape=should_trigger,
            rationale=rationale,
        )

        return delta

    def commit_delta(self, fresh_listings: List[ListingItem], delta: ParityDelta) -> None:
        """Persist fresh state to DuckDB and write audit log."""
        # 1. Upsert all fresh listings to advance last_seen_at & price
        for item in fresh_listings:
            self.store.upsert_listing(item)

        # 2. Log run audit
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.store.log_parity_run(
            run_id=run_id,
            query=delta.query,
            marketplace=delta.marketplace,
            total_scanned=delta.total_scanned,
            new_count=len(delta.new_listings),
            price_drop_count=len(delta.price_drops),
            unchanged_count=delta.unchanged_count,
            triggered_deep_scrape=delta.should_trigger_deep_scrape,
        )
        logger.info(f"Committed run {run_id} to DuckDB store.")

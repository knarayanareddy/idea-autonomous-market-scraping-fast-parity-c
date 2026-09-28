"""Data models for marketplace items, parity deltas, and crawler configurations."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class MarketplaceSource(str, Enum):
    EBAY = "ebay"
    MARKTPLAATS = "marktplaats"
    MOCK = "mock"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    PRICE_DROPPED = "price_dropped"
    PRICE_INCREASED = "price_increased"
    DELISTED = "delisted"


def generate_content_hash(external_id: str, title: str, price: float, currency: str) -> str:
    """Generate deterministic SHA-256 hash representing core item identity and price."""
    payload = f"{external_id}|{title.strip().lower()}|{price:.2f}|{currency.upper()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ListingItem(BaseModel):
    """Normalized listing from any marketplace."""

    external_id: str = Field(..., description="Unique ID on the marketplace")
    marketplace: MarketplaceSource = Field(..., description="Origin platform")
    title: str = Field(..., description="Item listing title")
    price: float = Field(..., description="Current listed price in float")
    currency: str = Field(default="EUR", description="Currency ISO code")
    url: str = Field(..., description="Canonical product URL")
    seller: Optional[str] = Field(default=None, description="Seller handle / username")
    location: Optional[str] = Field(default=None, description="Item geographic location")
    content_hash: str = Field(default="", description="Hash of content & pricing state")
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ListingStatus = Field(default=ListingStatus.ACTIVE)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            self.content_hash = generate_content_hash(
                self.external_id, self.title, self.price, self.currency
            )


class ParityDelta(BaseModel):
    """Computed difference between newly crawled listings and local state."""

    query: str
    marketplace: MarketplaceSource
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_scanned: int = 0
    new_listings: List[ListingItem] = Field(default_factory=list)
    price_drops: List[Tuple[ListingItem, float]] = Field(
        default_factory=list, description="List of (new_item, previous_price)"
    )
    price_increases: List[Tuple[ListingItem, float]] = Field(default_factory=list)
    unchanged_count: int = 0
    should_trigger_deep_scrape: bool = False
    rationale: str = ""

    def summary(self) -> Dict[str, Any]:
        """Return high-level metrics dictionary."""
        return {
            "query": self.query,
            "marketplace": self.marketplace.value,
            "total_scanned": self.total_scanned,
            "new_count": len(self.new_listings),
            "price_drops_count": len(self.price_drops),
            "price_increases_count": len(self.price_increases),
            "unchanged_count": self.unchanged_count,
            "trigger_apify": self.should_trigger_deep_scrape,
            "rationale": self.rationale,
        }

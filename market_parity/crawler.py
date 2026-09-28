"""Lightweight, resilient scraper client for marketplace search indexes."""

from __future__ import annotations

import logging
import random
import re
from typing import List, Optional
import urllib.parse

import requests
from bs4 import BeautifulSoup

from .models import ListingItem, MarketplaceSource

logger = logging.getLogger("market_parity.crawler")

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class MarketplaceCrawler:
    """Fast headless crawler to extract listing indexes before triggering heavy cloud jobs."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(DEFAULT_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Cache-Control": "no-cache",
        }

    def fetch_listings(
        self,
        query: str,
        source: MarketplaceSource = MarketplaceSource.MOCK,
        max_results: int = 20,
        simulated_scenario: Optional[str] = None,
    ) -> List[ListingItem]:
        """Fetch listing items for a given query and marketplace."""
        if source == MarketplaceSource.MOCK:
            return self._fetch_mock(query, max_results, scenario=simulated_scenario)
        elif source == MarketplaceSource.EBAY:
            return self._fetch_ebay(query, max_results)
        elif source == MarketplaceSource.MARKTPLAATS:
            return self._fetch_marktplaats(query, max_results)
        else:
            raise ValueError(f"Unsupported marketplace source: {source}")

    def _fetch_mock(
        self, query: str, max_results: int, scenario: Optional[str] = None
    ) -> List[ListingItem]:
        """Generate realistic, deterministic listings for testing and validation.

        Scenarios:
        - None / 'baseline': Normal set of items
        - 'price_drop': One item has a 20% reduced price
        - 'new_items': Extra newly posted items
        - 'unchanged': Identical items
        """
        base_items = [
            ("item-101", f"{query.title()} - Mint Condition in Box", 450.0, "EUR", "tech_seller_99", "Amsterdam"),
            ("item-102", f"{query.title()} Refurbished 16GB / 512GB SSD", 399.0, "EUR", "certified_resell", "Rotterdam"),
            ("item-103", f"Vintage {query.title()} Complete Collection", 620.0, "EUR", "collector_nl", "Utrecht"),
            ("item-104", f"{query.title()} for parts or repair", 120.0, "EUR", "hardware_fixer", "Eindhoven"),
            ("item-105", f"Custom Modded {query.title()} High Performance", 510.0, "EUR", "modmaster", "The Hague"),
        ]

        if scenario == "price_drop":
            # Item 101 drops from 450 to 380
            base_items[0] = ("item-101", base_items[0][1], 380.0, "EUR", "tech_seller_99", "Amsterdam")
        elif scenario == "new_items":
            base_items.append(
                ("item-106", f"Brand New Sealed {query.title()} 2026 Model", 699.0, "EUR", "deal_finder", "Groningen")
            )

        items: List[ListingItem] = []
        for ext_id, title, price, currency, seller, loc in base_items[:max_results]:
            items.append(
                ListingItem(
                    external_id=ext_id,
                    marketplace=MarketplaceSource.MOCK,
                    title=title,
                    price=price,
                    currency=currency,
                    url=f"https://marketplace.mock/item/{ext_id}",
                    seller=seller,
                    location=loc,
                )
            )
        return items

    def _fetch_ebay(self, query: str, max_results: int) -> List[ListingItem]:
        """Scrape public eBay search index."""
        url = f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote_plus(query)}&_sop=10"
        logger.info(f"Crawling eBay search index: {url}")

        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"eBay crawl failed: {exc}. Falling back to mock feed.")
            return self._fetch_mock(query, max_results)

        soup = BeautifulSoup(resp.text, "html.parser")
        listing_nodes = soup.select(".s-item__wrapper, .s-item")
        items: List[ListingItem] = []

        for node in listing_nodes:
            if len(items) >= max_results:
                break

            title_elem = node.select_one(".s-item__title")
            price_elem = node.select_one(".s-item__price")
            link_elem = node.select_one(".s-item__link")

            if not title_elem or not price_elem or not link_elem:
                continue

            title = title_elem.get_text(strip=True)
            if "shop on ebay" in title.lower():
                continue

            price_str = price_elem.get_text(strip=True)
            price_match = re.search(r"[\$€£]?\s*([0-9]+(?:[\.,][0-9]{2})?)", price_str)
            if not price_match:
                continue

            clean_price = float(price_match.group(1).replace(",", "."))
            currency = "USD" if "$" in price_str else "EUR"
            raw_url = link_elem.get("href", "")
            ext_id_match = re.search(r"/itm/([0-9]+)", raw_url)
            ext_id = ext_id_match.group(1) if ext_id_match else str(hash(raw_url))

            items.append(
                ListingItem(
                    external_id=ext_id,
                    marketplace=MarketplaceSource.EBAY,
                    title=title,
                    price=clean_price,
                    currency=currency,
                    url=raw_url,
                )
            )

        return items or self._fetch_mock(query, max_results)

    def _fetch_marktplaats(self, query: str, max_results: int) -> List[ListingItem]:
        """Scrape public Marktplaats search index."""
        url = f"https://www.marktplaats.nl/q/{urllib.parse.quote_plus(query)}/"
        logger.info(f"Crawling Marktplaats index: {url}")

        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"Marktplaats crawl failed: {exc}. Falling back to mock feed.")
            return self._fetch_mock(query, max_results)

        soup = BeautifulSoup(resp.text, "html.parser")
        items: List[ListingItem] = []

        # Parse listing cards
        cards = soup.select("li[class*='Listing'], a[class*='listing']")
        for card in cards:
            if len(items) >= max_results:
                break
            title_node = card.select_one("h3, [class*='title']")
            price_node = card.select_one("[class*='price']")
            if not title_node or not price_node:
                continue

            title = title_node.get_text(strip=True)
            price_str = price_node.get_text(strip=True)
            price_match = re.search(r"([0-9]+(?:[\.,][0-9]{2})?)", price_str)
            price = float(price_match.group(1).replace(",", ".")) if price_match else 0.0

            href = card.get("href") or (card.find("a") and card.find("a").get("href")) or ""
            full_url = f"https://www.marktplaats.nl{href}" if href.startswith("/") else href
            ext_id = re.search(r"m[0-9]+", full_url)
            ext_id_str = ext_id.group(0) if ext_id else str(hash(full_url))

            items.append(
                ListingItem(
                    external_id=ext_id_str,
                    marketplace=MarketplaceSource.MARKTPLAATS,
                    title=title,
                    price=price,
                    currency="EUR",
                    url=full_url,
                )
            )

        return items or self._fetch_mock(query, max_results)

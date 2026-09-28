import tempfile
import unittest
from pathlib import Path
from market_parity.crawler import MarketplaceCrawler
from market_parity.database import DuckDBMarketStore
from market_parity.models import MarketplaceSource
from market_parity.parity_checker import ParityChecker


class TestParityChecker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
        self.tmp.close()
        self.store = DuckDBMarketStore(db_path=self.tmp.name)
        self.checker = ParityChecker(self.store)
        self.crawler = MarketplaceCrawler()

    def tearDown(self):
        self.store.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_first_run_detects_all_new(self):
        listings = self.crawler.fetch_listings("ThinkPad", source=MarketplaceSource.MOCK)
        delta = self.checker.evaluate_parity("ThinkPad", MarketplaceSource.MOCK, listings)

        self.assertEqual(len(delta.new_listings), len(listings))
        self.assertTrue(delta.should_trigger_deep_scrape)

        # Commit delta
        self.checker.commit_delta(listings, delta)

        # Second run with exact same listings should be 100% in parity
        delta2 = self.checker.evaluate_parity("ThinkPad", MarketplaceSource.MOCK, listings)
        self.assertEqual(len(delta2.new_listings), 0)
        self.assertEqual(delta2.unchanged_count, len(listings))
        self.assertFalse(delta2.should_trigger_deep_scrape)

    def test_price_drop_triggers_scrape(self):
        # Initial baseline
        listings = self.crawler.fetch_listings("ThinkPad", source=MarketplaceSource.MOCK)
        delta = self.checker.evaluate_parity("ThinkPad", MarketplaceSource.MOCK, listings)
        self.checker.commit_delta(listings, delta)

        # Scrape with price drop scenario
        price_drop_listings = self.crawler.fetch_listings(
            "ThinkPad", source=MarketplaceSource.MOCK, simulated_scenario="price_drop"
        )
        delta_drop = self.checker.evaluate_parity(
            "ThinkPad", MarketplaceSource.MOCK, price_drop_listings
        )

        self.assertEqual(len(delta_drop.price_drops), 1)
        self.assertTrue(delta_drop.should_trigger_deep_scrape)
        self.assertEqual(delta_drop.price_drops[0][1], 450.0)  # old price
        self.assertEqual(delta_drop.price_drops[0][0].price, 380.0)  # new price


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from market_parity.database import DuckDBMarketStore
from market_parity.models import ListingItem, MarketplaceSource


class TestDuckDBStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
        self.tmp.close()
        self.store = DuckDBMarketStore(db_path=self.tmp.name)

    def tearDown(self):
        self.store.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_upsert_and_fetch(self):
        item = ListingItem(
            external_id="item_1",
            marketplace=MarketplaceSource.MOCK,
            title="MacBook Air M2",
            price=800.0,
            currency="EUR",
            url="https://mock.market/item_1",
        )
        is_new = self.store.upsert_listing(item)
        self.assertTrue(is_new)

        fetched = self.store.get_listing(MarketplaceSource.MOCK, "item_1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "MacBook Air M2")
        self.assertEqual(fetched.price, 800.0)

        # Update price
        item.price = 750.0
        is_new2 = self.store.upsert_listing(item)
        self.assertFalse(is_new2)

        fetched2 = self.store.get_listing(MarketplaceSource.MOCK, "item_1")
        self.assertEqual(fetched2.price, 750.0)

    def test_stats(self):
        stats = self.store.get_stats()
        self.assertEqual(stats["total_tracked_listings"], 0)


if __name__ == "__main__":
    unittest.main()

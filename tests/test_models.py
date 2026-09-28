import unittest
from market_parity.models import ListingItem, MarketplaceSource, generate_content_hash


class TestModels(unittest.TestCase):
    def test_content_hash_deterministic(self):
        h1 = generate_content_hash("123", "ThinkPad X1 Carbon", 500.0, "EUR")
        h2 = generate_content_hash("123", "Thinkpad X1 Carbon ", 500.0, "eur")
        self.assertEqual(h1, h2)

    def test_listing_item_auto_hash(self):
        item = ListingItem(
            external_id="ebay_999",
            marketplace=MarketplaceSource.EBAY,
            title="Vintage Camera",
            price=150.0,
            currency="EUR",
            url="https://ebay.com/itm/999",
        )
        self.assertTrue(len(item.content_hash) == 64)
        self.assertEqual(item.status.value, "active")


if __name__ == "__main__":
    unittest.main()

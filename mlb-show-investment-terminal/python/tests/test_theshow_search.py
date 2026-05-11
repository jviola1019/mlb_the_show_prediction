import unittest

from mlb_show_terminal import theshow


class TheShowSearchTests(unittest.TestCase):
    def test_normalize_name_preserves_suffix_and_reverses_commas(self):
        self.assertEqual(theshow.normalize_name("  Trout, Mike  "), "Mike Trout")
        self.assertEqual(theshow.normalize_name("Ronald Acuna Jr."), "Ronald Acuna Jr.")

    def test_search_match_exact_and_partial_scores(self):
        exact = theshow.search_match("Mike Trout", "Mike Trout")
        partial = theshow.search_match("Mike", "Mike Trout")
        self.assertTrue(exact["exact_name_match"])
        self.assertFalse(partial["exact_name_match"])
        self.assertGreater(exact["match_score"], partial["match_score"])

    def test_search_card_annotates_and_sorts_exact_matches_first(self):
        original = theshow.request_with_year
        theshow.search_card.cache_clear()

        def fake_request(path, query, years):
            self.assertEqual(query["name"], "Mike Trout")
            return {
                "_year_used": 26,
                "_source_url": "https://example.test",
                "listings": [
                    {"listing_name": "Mike Napoli", "item": {"uuid": "1" * 32, "name": "Mike Napoli"}},
                    {"listing_name": "Mike Trout", "item": {"uuid": "2" * 32, "name": "Mike Trout"}},
                ],
            }

        try:
            theshow.request_with_year = fake_request
            payload = theshow.search_card(" Trout, Mike ", year=26)
        finally:
            theshow.request_with_year = original
            theshow.search_card.cache_clear()

        self.assertEqual(payload["normalized_query"], "Mike Trout")
        self.assertEqual(payload["listings"][0]["item"]["name"], "Mike Trout")
        self.assertTrue(payload["listings"][0]["search"]["exact_name_match"])

    def test_discover_top_listings_filters_rarity(self):
        original = theshow.request_with_year
        theshow.discover_top_listings.cache_clear()

        def fake_request(path, query, years):
            return {
                "_year_used": 26,
                "_source_url": "https://example.test",
                "listings": [
                    {"best_sell_price": 10, "item": {"uuid": "1" * 32, "name": "A", "rarity": "Silver"}},
                    {"best_sell_price": 30, "item": {"uuid": "2" * 32, "name": "B", "rarity": "Gold"}},
                    {"best_sell_price": 20, "item": {"uuid": "3" * 32, "name": "C", "rarity": "Gold"}},
                ],
            }

        try:
            theshow.request_with_year = fake_request
            payload = theshow.discover_top_listings("Gold", top_n=2, year=26, pages=1)
        finally:
            theshow.request_with_year = original
            theshow.discover_top_listings.cache_clear()

        self.assertEqual(payload["uuids"], ["2" * 32, "3" * 32])
        self.assertEqual(len(payload["listings"]), 2)


if __name__ == "__main__":
    unittest.main()

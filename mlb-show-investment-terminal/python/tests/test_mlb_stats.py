import unittest
from datetime import date

from mlb_show_terminal import mlb_stats


class MLBStatsTests(unittest.TestCase):
    def tearDown(self):
        mlb_stats.search_player.cache_clear()
        mlb_stats.player_stats.cache_clear()

    def test_recent_vs_season_uses_api_shape_for_hitter(self):
        original_get = mlb_stats._get_json

        def fake_get(path, query=None, timeout=15.0):
            if path == "/api/v1/people/search":
                return {
                    "people": [
                        {
                            "id": 545361,
                            "fullName": "Mike Trout",
                            "primaryPosition": {"name": "Outfielder", "code": "8"},
                        }
                    ]
                }
            return {"stats": [{"splits": [{"stat": {"ops": ".950", "avg": ".320", "plateAppearances": "42"}}]}]}

        try:
            mlb_stats._get_json = fake_get
            payload = mlb_stats.recent_vs_season("Mike Trout", today=date(2026, 5, 6))
        finally:
            mlb_stats._get_json = original_get

        self.assertEqual(payload["role"], "hitter")
        self.assertEqual(payload["player"]["full_name"], "Mike Trout")
        self.assertAlmostEqual(payload["recent"]["ops"], 0.95)
        self.assertEqual(payload["recent_start"], "2026-04-22")
        self.assertEqual(payload["season_start"], "2026-03-01")

    def test_missing_player_returns_empty_stats(self):
        original_get = mlb_stats._get_json

        def fake_get(path, query=None, timeout=15.0):
            return {"people": []}

        try:
            mlb_stats._get_json = fake_get
            payload = mlb_stats.recent_vs_season("No Match", role="pitcher", today=date(2026, 5, 6))
        finally:
            mlb_stats._get_json = original_get

        self.assertIsNone(payload["player"])
        self.assertEqual(payload["role"], "pitcher")
        self.assertEqual(payload["recent"], {})


if __name__ == "__main__":
    unittest.main()

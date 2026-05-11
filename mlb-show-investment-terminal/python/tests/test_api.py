import unittest
import time
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from mlb_show_terminal.api import create_app


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_contract(self):
        payload = self.client.get("/api/health").json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["quant_owner"], "python")

    def test_static_serving_smoke_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "index.html").write_text('<div id="root"></div><script type="module" src="/assets/app.js"></script>', encoding="utf-8")
            (root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
            client = TestClient(create_app(static_dir=root))
            self.assertEqual(client.get("/api/health").json()["status"], "ok")
            html = client.get("/")
            self.assertEqual(html.status_code, 200)
            self.assertIn("/assets/app.js", html.text)
            asset = client.get("/assets/app.js")
            self.assertEqual(asset.status_code, 200)
            self.assertIn("console.log", asset.text)

    def test_upgrade_score_contract(self):
        res = self.client.post(
            "/api/upgrade/score",
            json={
                "recent": {"ops": 0.950, "avg": 0.320, "plateAppearances": 42},
                "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
                "role": "hitter",
                "current_ovr": 84,
                "rarity": "Gold",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("p_cross_next_threshold", res.json())

    def test_session_summary_contract(self):
        res = self.client.get("/api/session/summary")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload["status"], "stateless")
        self.assertEqual(payload["runtime_writes"], "prohibited")

    def test_mlb_stats_contract_without_player(self):
        from mlb_show_terminal import mlb_stats

        original = mlb_stats.search_player
        mlb_stats.search_player.cache_clear()
        try:
            mlb_stats.search_player = lambda name: None
            res = self.client.get("/api/mlb/player-stats?name=Nope&role=auto")
        finally:
            mlb_stats.search_player = original
            original.cache_clear()
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()["player"])

    def test_scan_rows_partition_contract(self):
        res = self.client.post(
            "/api/scan",
            json={
                "rows": [
                    {
                        "uuid": "a",
                        "name": "Flip",
                        "raw_ask": 1538,
                        "raw_bid": 1120,
                        "liquidity_score": 1,
                        "current_ovr": 84,
                        "rarity": "Gold",
                    }
                ]
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload["counts"]["flip_buys"], 1)
        self.assertIn("progress", payload)
        row = payload["partitions"]["flip_buys"][0]
        self.assertEqual(row["flip_action"], "BUY")
        self.assertIn("after_tax_sale", row)
        self.assertIn("gates_failed_csv", row)
        self.assertIn("market_health", payload)

    def test_scan_job_lifecycle_with_fixture_rows(self):
        res = self.client.post(
            "/api/scan/jobs",
            json={
                "rows": [
                    {
                        "uuid": "a",
                        "name": "Flip",
                        "raw_ask": 1538,
                        "raw_bid": 1120,
                        "liquidity_score": 1,
                        "current_ovr": 84,
                        "rarity": "Gold",
                    }
                ],
                "rate_delay": 0,
            },
        )
        self.assertEqual(res.status_code, 200)
        job_id = res.json()["job_id"]
        payload = {}
        for _ in range(20):
            payload = self.client.get(f"/api/scan/jobs/{job_id}").json()
            if payload["status"] == "complete":
                break
            time.sleep(0.05)
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["completed"], 1)
        self.assertEqual(payload["result"]["counts"]["flip_buys"], 1)

    def test_card_validate_contract(self):
        res = self.client.post("/api/card/validate", json={"sell_price": 1538, "buy_price": 1120})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["validation"]["mismatch"])

    def test_parity_audit_contract(self):
        res = self.client.get("/api/audit/parity")
        self.assertEqual(res.status_code, 200)
        self.assertIn("features", res.json())
        self.assertTrue(any(row["feature_id"] == "market_scan.partitions" for row in res.json()["features"]))

    def test_analyze_listing_returns_forecast_diagnostics(self):
        listing = {
            "best_sell_price": 1538,
            "best_buy_price": 1120,
            "item": {"uuid": "a" * 32, "name": "Fixture", "rarity": "Gold", "ovr": 84},
            "completed_orders": [{"price": str(1200 + (idx % 7) * 4)} for idx in range(60)],
        }
        res = self.client.post("/api/card/analyze", json={"listing": listing})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertIn("cone", payload["forecast"])
        self.assertIn("horizons", payload["forecast"])
        self.assertIn("walk_forward", payload["forecast"])

    def test_scan_enriches_mlb_stats_server_side_when_enabled(self):
        from mlb_show_terminal import scan as scan_module

        original = scan_module.recent_vs_season
        try:
            scan_module.recent_vs_season = lambda name: {
                "recent": {"ops": 1.000, "avg": 0.330, "plateAppearances": 44},
                "season": {"ops": 0.760, "avg": 0.260, "plateAppearances": 190},
                "role": "hitter",
                "player": {"id": 1, "full_name": name},
            }
            listing = {
                "best_sell_price": 1538,
                "best_buy_price": 1120,
                "item": {"uuid": "b" * 32, "name": "Server Stats", "rarity": "Gold", "ovr": 84},
                "completed_orders": [{"price": str(1200 + (idx % 7) * 4)} for idx in range(60)],
            }
            payload = scan_module.analyze_listing(listing, enrich_mlb_stats=True)
        finally:
            scan_module.recent_vs_season = original
        self.assertEqual(payload["card"]["role"], "hitter")
        self.assertGreater(payload["upgrade"]["p_cross_next_threshold"], 0)

    def test_backtest_unavailable_without_labels(self):
        res = self.client.post(
            "/api/backtest/upgrades",
            json={"predictions": [{"uuid": "a", "p_cross_next_threshold": 0.7}], "labels": []},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()

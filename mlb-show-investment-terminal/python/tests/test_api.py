import unittest
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from mlb_show_terminal.api import create_app


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_contract(self):
        payload = self.client.get("/api/health").json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["quant_owner"], "python")

    def test_cors_allowlist_is_not_wildcard_by_default(self):
        res = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertNotEqual(res.headers.get("access-control-allow-origin"), "*")

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
        self.assertEqual(payload["runtime_writes"]["credential_exposure"], "none")

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
        self.assertEqual(payload["counts"]["watch"], 1)
        self.assertIn("progress", payload)
        row = payload["partitions"]["watch"][0]
        self.assertEqual(row["flip_action"], "BUY")
        self.assertEqual(row["decision_action"], "WATCHLIST / NO MODEL TRADE")
        self.assertEqual(row["strategy"]["flip"]["verdict"], "FLIP PASS")
        self.assertIn("data_coverage_tier", row)
        self.assertIn("performance_validation_tier", row)
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
        self.assertEqual(payload["result"]["counts"]["watch"], 1)

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
        self.assertEqual(payload["collection_status"]["status"], "skipped")
        self.assertEqual(payload["prediction_collection_status"]["status"], "skipped")

    def test_public_analyze_only_collects_with_write_token(self):
        listing = {
            "best_sell_price": 1538,
            "best_buy_price": 1120,
            "item": {"uuid": "f" * 32, "name": "Persist Fixture", "rarity": "Gold", "ovr": 84},
            "completed_orders": [{"price": str(1200 + (idx % 7) * 4)} for idx in range(60)],
        }
        with patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service",
                "TERMINAL_WRITE_TOKEN": "expected",
            },
            clear=True,
        ):
            client = TestClient(create_app())
            no_token = client.post("/api/card/analyze", json={"listing": listing})
            self.assertEqual(no_token.status_code, 200)
            self.assertEqual(no_token.json()["collection_status"]["status"], "skipped")
            with (
                patch("mlb_show_terminal.scan.collect_market_snapshot", return_value={"status": "ok", "table": "market_snapshots"}),
                patch("mlb_show_terminal.scan.collect_model_prediction", return_value={"status": "ok", "table": "model_predictions"}),
            ):
                ok = client.post(
                    "/api/card/analyze",
                    json={"listing": listing},
                    headers={"x-terminal-write-token": "expected"},
                )
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.json()["collection_status"]["status"], "ok")

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
        self.assertIn("confusion", res.json())

    def test_backtest_accepts_schema_and_threshold_controls(self):
        res = self.client.post(
            "/api/backtest/upgrades",
            json={
                "predictions": [
                    {"id": "a", "prob": 0.60},
                    {"id": "b", "prob": 0.40},
                ],
                "labels": [
                    {"id": "a", "outcome": "true"},
                    {"id": "b", "outcome": "false"},
                ],
                "id_col": "id",
                "prob_col": "prob",
                "outcome_col": "outcome",
                "decision_threshold": 0.55,
                "n_bins": 2,
                "min_n": 1,
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["n"], 2)
        self.assertEqual(payload["decision_threshold"], 0.55)

    def test_completed_order_backtest_route_uses_sale_snapshots(self):
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "c" * 32,
            "item": {"uuid": "c" * 32, "name": "Backtest Fixture"},
            "completed_orders": [
                {"date": f"2026-05-{1 + (idx // 2):02d}T{(idx % 2) * 12:02d}:00:00Z", "price": str(1000 + idx * 25)}
                for idx in range(28)
            ],
        }
        res = self.client.post(
            "/api/backtest/completed-orders",
            json={
                "listings": [listing],
                "min_orders": 10,
                "lookback_orders": 6,
                "horizons_days": [1],
                "tax_rate": 0,
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["snapshot_kind"], "historical_completed_sale")
        self.assertIn("data_coverage_tier", payload)
        self.assertIn("performance_validation_tier", payload)
        self.assertEqual(payload["data_coverage_source"], "COMPLETED_SALES_ONLY")
        self.assertIn("completed_orders", payload["source_limitations"][0])
        self.assertEqual(payload["leakage_guard"]["future_features_allowed"], False)

    def test_historical_snapshot_backtest_route_uses_price_history_bid_ask(self):
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "e" * 32,
            "item": {"uuid": "e" * 32, "name": "Snapshot Fixture"},
            "price_history": [
                {"date": f"2026-04-{1 + idx:02d}T00:00:00Z", "best_buy_price": 1000 + idx * 25, "best_sell_price": 1150 + idx * 25}
                for idx in range(28)
            ],
        }
        res = self.client.post(
            "/api/backtest/historical-snapshots",
            json={
                "listings": [listing],
                "min_snapshots": 10,
                "lookback_snapshots": 6,
                "horizons_days": [1],
                "tax_rate": 0,
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["snapshot_kind"], "historical_bid_ask_snapshot")
        self.assertIn("data_coverage_tier", payload)
        self.assertIn("performance_validation_tier", payload)
        self.assertEqual(payload["data_coverage_source"], "HISTORICAL_BID_ASK_HISTORY")
        self.assertIn("price_history", payload["source"])
        self.assertEqual(payload["leakage_guard"]["future_features_allowed"], False)

    def test_ledger_log_requires_write_token_when_persistence_configured(self):
        row = {
            "card_uuid": "a" * 32,
            "buy_price": 1000,
            "timestamp": "2026-05-14T00:00:00Z",
            "strategy_type": "flip",
        }
        with patch.dict(
            "os.environ",
            {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "service"},
            clear=True,
        ):
            client = TestClient(create_app())
            res = client.post("/api/ledger/log", json={"row": row})
            self.assertEqual(res.status_code, 503)

        with patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service",
                "TERMINAL_WRITE_TOKEN": "expected",
            },
            clear=True,
        ):
            client = TestClient(create_app())
            self.assertEqual(client.post("/api/ledger/log", json={"row": row}).status_code, 403)
            with patch("mlb_show_terminal.api.persist_ledger_row", return_value={"status": "ok"}):
                ok = client.post(
                    "/api/ledger/log",
                    json={"row": row},
                    headers={"x-terminal-write-token": "expected"},
                )
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()

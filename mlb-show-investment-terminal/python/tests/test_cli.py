import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_score_row_cli_writes_python_backend_payload(self):
        row = {
            "raw_ask": 1538,
            "raw_bid": 1120,
            "liquidity_score": 1,
            "liquidity_n": 8,
            "liquidity_recent": 3,
            "current_ovr": 84,
            "rarity": "gold",
            "recent": {"ops": 0.950, "avg": 0.320, "plateAppearances": 42},
            "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
        }
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.json"
            out = Path(tmp) / "output.json"
            inp.write_text(json.dumps(row), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlb_show_terminal.cli",
                    "score-row",
                    "--input",
                    str(inp),
                    "--output",
                    str(out),
                ],
                check=True,
            )
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload["python_backend"])
        self.assertEqual(payload["flip"]["action"], "BUY")
        self.assertIn("PYTHON_BACKEND", payload["upgrade"]["reason_codes"])
        self.assertFalse(payload["validation"]["mismatch"])

    def test_backfill_upgrades_cli_writes_outputs(self):
        pre_rows = [
            {
                "uuid": "a",
                "name": "A",
                "ovr": 84,
                "rarity": "Gold",
                "raw_ask": 1538,
                "raw_bid": 1120,
                "liquidity_score": 1,
                "recent": {"ops": 0.950, "avg": 0.320, "plateAppearances": 42},
                "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
            },
            {
                "uuid": "b",
                "name": "B",
                "ovr": 84,
                "rarity": "Gold",
                "raw_ask": 1400,
                "raw_bid": 1200,
                "liquidity_score": 1,
                "recent": {"ops": 0.650, "avg": 0.220, "plateAppearances": 35},
                "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
            },
        ]
        post_rows = [
            {"uuid": "a", "name": "A", "ovr": 85, "rarity": "Diamond"},
            {"uuid": "b", "name": "B", "ovr": 84, "rarity": "Gold"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            pre = Path(tmp) / "pre.json"
            post = Path(tmp) / "post.json"
            out = Path(tmp) / "backfill"
            pre.write_text(json.dumps(pre_rows), encoding="utf-8")
            post.write_text(json.dumps(post_rows), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlb_show_terminal.cli",
                    "backfill-upgrades",
                    "--pre",
                    str(pre),
                    "--post",
                    str(post),
                    "--output-dir",
                    str(out),
                    "--min-n",
                    "1",
                ],
                check=True,
            )
            backtest = json.loads((out / "backtest.json").read_text(encoding="utf-8"))
        self.assertEqual(backtest["status"], "available")
        self.assertEqual(backtest["n"], 2)

    def test_backtest_completed_orders_cli_writes_limited_validation(self):
        orders = [
            {"date": f"2026-05-{1 + (idx // 2):02d}T{(idx % 2) * 12:02d}:00:00Z", "price": str(1000 + idx * 25)}
            for idx in range(28)
        ]
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "d" * 32,
            "item": {"uuid": "d" * 32, "name": "CLI Backtest Fixture"},
            "completed_orders": orders,
        }
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "listing.json"
            out = Path(tmp) / "completed-order-backtest.json"
            inp.write_text(json.dumps([listing]), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlb_show_terminal.cli",
                    "backtest-completed-orders",
                    "--listings",
                    str(inp),
                    "--output",
                    str(out),
                    "--min-orders",
                    "10",
                    "--lookback-orders",
                    "6",
                    "--horizons",
                    "1",
                    "--tax-rate",
                    "0",
                ],
                check=True,
            )
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["snapshot_kind"], "historical_completed_sale")
        self.assertEqual(payload["leakage_guard"]["future_features_allowed"], False)

    def test_backtest_historical_snapshots_cli_writes_bid_ask_validation(self):
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "f" * 32,
            "item": {"uuid": "f" * 32, "name": "CLI Snapshot Fixture"},
            "price_history": [
                {"date": f"2026-04-{1 + idx:02d}T00:00:00Z", "best_buy_price": 1000 + idx * 25, "best_sell_price": 1150 + idx * 25}
                for idx in range(28)
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "listing.json"
            out = Path(tmp) / "historical-snapshot-backtest.json"
            inp.write_text(json.dumps([listing]), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlb_show_terminal.cli",
                    "backtest-historical-snapshots",
                    "--listings",
                    str(inp),
                    "--output",
                    str(out),
                    "--min-snapshots",
                    "10",
                    "--lookback-snapshots",
                    "6",
                    "--horizons",
                    "1",
                    "--tax-rate",
                    "0",
                ],
                check=True,
            )
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["snapshot_kind"], "historical_bid_ask_snapshot")
        self.assertEqual(payload["leakage_guard"]["future_features_allowed"], False)


if __name__ == "__main__":
    unittest.main()

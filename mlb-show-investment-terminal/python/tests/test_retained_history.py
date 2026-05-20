import unittest

from mlb_show_terminal.retained_history import summarize_external_ledger, summarize_retained_market_history


class RetainedHistoryTests(unittest.TestCase):
    def test_summarize_retained_history_counts_real_rows(self):
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "a" * 32,
            "item": {"uuid": "a" * 32, "name": "Fixture", "rarity": "Gold"},
            "price_history": [
                {"date": f"2026-04-{idx + 1:02d}T00:00:00Z", "best_buy_price": 1000 + idx, "best_sell_price": 1200 + idx}
                for idx in range(10)
            ],
            "completed_orders": [
                {"date": f"2026-05-{idx + 1:02d}T00:00:00Z", "price": str(1000 + idx)}
                for idx in range(10)
            ],
        }
        result = summarize_retained_market_history([listing], include_rows=True)
        self.assertEqual(result["cards_fetched"], 1)
        self.assertEqual(result["historical_bid_ask_snapshots_found"], 10)
        self.assertEqual(result["completed_sale_snapshots_found"], 10)
        self.assertEqual(result["sample_cards"][0]["price_history_rows"], 10)
        self.assertIn("historical_bid_ask_snapshots", result)
        self.assertIn("data_coverage_tier", result["historical_snapshot_backtest"])
        self.assertIn("performance_validation_tier", result["historical_snapshot_backtest"])
        self.assertIn("data_coverage_tier", result["completed_order_backtest"])
        self.assertIn("performance_validation_tier", result["completed_order_backtest"])

    def test_external_ledger_summary_normalizes_user_supplied_rows(self):
        result = summarize_external_ledger(
            [
                {
                    "uuid": "b" * 32,
                    "name": "Manual Flip",
                    "buy": "1000",
                    "sell": "1250",
                    "date": "2026-05-14T00:00:00Z",
                    "strategy": "flip",
                    "expected_profit": "80",
                },
                {"uuid": "bad"},
            ],
            source_name="unit_test",
        )
        self.assertEqual(result["rows_received"], 2)
        self.assertEqual(result["valid_rows"], 1)
        self.assertEqual(result["invalid_rows"], 1)
        self.assertEqual(result["metrics"]["closed_trades"], 1)
        self.assertGreater(result["metrics"]["realized_profit"], 0)

    def test_external_ledger_summary_accepts_bom_csv_headers(self):
        result = summarize_external_ledger(
            [
                {
                    "\ufeffcard_uuid": "c" * 32,
                    "card_name": "BOM Export",
                    "buy_price": "1000",
                    "sell_price": "1200",
                    "timestamp": "2026-05-14T00:00:00Z",
                    "strategy_type": "flip",
                }
            ],
            source_name="bom_export",
        )
        self.assertEqual(result["valid_rows"], 1)
        self.assertEqual(result["invalid_rows"], 0)
        self.assertEqual(result["normalized_rows"][0]["card_uuid"], "c" * 32)


if __name__ == "__main__":
    unittest.main()

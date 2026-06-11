import unittest
from datetime import datetime, timedelta, timezone

from mlb_show_terminal.completed_order_backtesting import (
    completed_order_snapshots_from_listing,
    evaluate_completed_order_backtest,
    evaluate_historical_snapshot_backtest,
    historical_market_snapshots_from_listing,
)


def _listing(uuid: str = "a" * 32, *, n: int = 40, step_hours: int = 12, drift: int = 25) -> dict:
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    orders = []
    for idx in range(n):
        ts = start + timedelta(hours=step_hours * idx)
        orders.append({"date": ts.isoformat().replace("+00:00", "Z"), "price": str(1000 + drift * idx)})
    return {
        "source_url": f"https://mlb26.theshow.com/apis/listing.json?uuid={uuid}",
        "item": {"uuid": uuid, "name": "Fixture Card"},
        "completed_orders": orders,
    }


def _price_history_listing(uuid: str = "b" * 32, *, n: int = 40, drift: int = 25) -> dict:
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    rows = []
    for idx in range(n):
        ts = start + timedelta(days=idx)
        bid = 1000 + idx * drift
        ask = bid + 150
        rows.append({"date": ts.isoformat().replace("+00:00", "Z"), "best_buy_price": bid, "best_sell_price": ask})
    return {
        "source_url": f"https://mlb26.theshow.com/apis/listing.json?uuid={uuid}",
        "item": {"uuid": uuid, "name": "History Fixture"},
        "price_history": rows,
    }


class CompletedOrderBacktestingTests(unittest.TestCase):
    def test_completed_order_snapshots_use_real_sale_prices_only(self):
        rows = completed_order_snapshots_from_listing(_listing(n=3))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["sale_price"], 1000.0)
        self.assertEqual(rows[0]["snapshot_kind"], "historical_completed_sale")
        self.assertNotIn("raw_ask", rows[0])
        self.assertNotIn("raw_bid", rows[0])

    def test_completed_order_backtest_is_rolling_origin_and_limited(self):
        first = evaluate_completed_order_backtest(
            [_listing()],
            min_orders=10,
            lookback_orders=6,
            horizons_days=[1, 3],
            tax_rate=0,
        )
        second = evaluate_completed_order_backtest(
            [{"records": []}, _listing()],
            min_orders=10,
            lookback_orders=6,
            horizons_days=[3, 1],
            tax_rate=0,
        )
        self.assertEqual(first["status"], "available")
        self.assertEqual(first["validation_tier"], "BRONZE")
        self.assertEqual(first["data_coverage_tier"], "BRONZE")
        self.assertEqual(first["performance_validation_tier"], "BRONZE")
        self.assertEqual(first["data_coverage_source"], "COMPLETED_SALES_ONLY")
        self.assertEqual(first["leakage_guard"]["future_features_allowed"], False)
        self.assertIn("completed_orders provide historical sale prices", first["source_limitations"][0])
        self.assertIn("naive_spread_only", first["baselines"])
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertGreater(first["evaluated_opportunities"], 0)

    def test_completed_order_backtest_requires_enough_real_history(self):
        result = evaluate_completed_order_backtest([_listing(n=5)], min_orders=10, lookback_orders=3)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["validation_tier"], "UNVALIDATED")
        self.assertEqual(result["performance_validation_tier"], "UNVALIDATED")
        self.assertEqual(result["data_coverage_source"], "INSUFFICIENT_REAL_HISTORY")
        self.assertIn("INSUFFICIENT_REAL_COMPLETED_ORDER_HISTORY", result["reason_codes"])

    def test_price_history_snapshots_keep_real_bid_ask(self):
        rows = historical_market_snapshots_from_listing(_price_history_listing(n=3))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["snapshot_kind"], "historical_bid_ask_snapshot")
        self.assertEqual(rows[0]["raw_bid"], 1000.0)
        self.assertEqual(rows[0]["raw_ask"], 1150.0)

    def test_historical_snapshot_backtest_uses_bid_ask_without_future_features(self):
        result = evaluate_historical_snapshot_backtest(
            [_price_history_listing()],
            min_snapshots=10,
            lookback_snapshots=6,
            horizons_days=[1, 3],
            tax_rate=0,
        )
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["snapshot_kind"], "historical_bid_ask_snapshot")
        self.assertEqual(result["data_coverage_source"], "HISTORICAL_BID_ASK_HISTORY")
        self.assertIn(result["performance_validation_tier"], {"BRONZE", "UNVALIDATED"})
        self.assertEqual(result["leakage_guard"]["future_features_allowed"], False)
        self.assertIn("naive_spread_only", result["baselines"])
        self.assertGreater(result["evaluated_opportunities"], 0)
        self.assertIn("execution_assumption", result["sample_predictions"][0])

    def test_historical_directional_hold_uses_conservative_ask_to_future_bid(self):
        rows = historical_market_snapshots_from_listing(_price_history_listing(n=15, drift=25))
        listing = {
            "source_url": "https://mlb26.theshow.com/apis/listing.json?uuid=" + "c" * 32,
            "item": {"uuid": "c" * 32, "name": "History Fixture"},
            "price_history": [
                {"date": row["timestamp"], "best_buy_price": row["raw_bid"], "best_sell_price": row["raw_ask"]}
                for row in rows
            ],
        }
        result = evaluate_historical_snapshot_backtest(
            [listing],
            min_snapshots=10,
            lookback_snapshots=3,
            horizons_days=[1],
            tax_rate=0,
        )
        hold_rows = [row for row in result["sample_predictions"] if row["strategy_family"] in {"directional_hold", "flip_or_short_hold"}]
        self.assertTrue(hold_rows)
        first = hold_rows[0]
        self.assertGreater(first["entry_price"], first["exit_price"])
        self.assertIn("buy at current ask", first["execution_assumption"])


if __name__ == "__main__":
    unittest.main()

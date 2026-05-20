import unittest

from mlb_show_terminal.backtesting import evaluate_strategy_backtest


class StrategyBacktestingTests(unittest.TestCase):
    def test_strategy_backtest_requires_real_snapshots(self):
        result = evaluate_strategy_backtest([], min_snapshots=2)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["validation_tier"], "UNVALIDATED")
        self.assertEqual(result["data_coverage_tier"], "UNVALIDATED")
        self.assertEqual(result["performance_validation_tier"], "UNVALIDATED")
        self.assertEqual(result["data_coverage_source"], "INSUFFICIENT_REAL_HISTORY")
        self.assertIn("INSUFFICIENT_REAL_MARKET_SNAPSHOTS", result["reason_codes"])
        self.assertIn("naive_spread_only", result["baselines"])

    def test_strategy_backtest_is_deterministic_on_timestamped_snapshots(self):
        snapshots = [
            {
                "card_uuid": "a",
                "pulled_at": "2026-05-13T00:00:00Z",
                "raw_ask": 1200,
                "raw_bid": 1000,
                "strategy": {"composite": {"final_action": "INSTANT FLIP ONLY"}},
            },
            {
                "card_uuid": "a",
                "pulled_at": "2026-05-14T00:00:00Z",
                "raw_ask": 1300,
                "raw_bid": 1100,
                "strategy": {"composite": {"final_action": "WATCHLIST / NO MODEL TRADE"}},
            },
            {
                "card_uuid": "b",
                "pulled_at": "2026-05-13T00:00:00Z",
                "raw_ask": 900,
                "raw_bid": 800,
                "strategy": {"composite": {"final_action": "AVOID"}},
            },
        ]
        first = evaluate_strategy_backtest(snapshots, min_snapshots=3)
        second = evaluate_strategy_backtest(list(reversed(snapshots)), min_snapshots=3)
        self.assertEqual(first["status"], "available")
        self.assertEqual(first["trades_taken"], 1)
        self.assertIn(first["performance_validation_tier"], {"BRONZE", "UNVALIDATED"})
        self.assertEqual(first["data_coverage_source"], "RETAINED_MARKET_SNAPSHOTS")
        self.assertIn("execution_assumption", first["sample_predictions"][0])
        self.assertIn("baseline_comparison", first)
        self.assertEqual(first["metrics"], second["metrics"])

    def test_coverage_does_not_promote_losing_performance(self):
        snapshots = [
            {
                "card_uuid": "a",
                "pulled_at": f"2026-05-{idx + 1:02d}T00:00:00Z",
                "raw_ask": 1000,
                "raw_bid": 1000,
                "strategy": {"composite": {"final_action": "SPECULATIVE HOLD"}},
            }
            for idx in range(31)
        ]
        result = evaluate_strategy_backtest(snapshots, min_snapshots=30)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data_coverage_tier"], "BRONZE")
        self.assertEqual(result["performance_validation_tier"], "BRONZE")
        self.assertEqual(result["validation_verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()

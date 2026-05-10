import unittest

from mlb_show_terminal.historical import evaluate_backtest


class HistoricalBacktestTests(unittest.TestCase):
    def test_missing_labels_are_unavailable(self):
        result = evaluate_backtest(
            [{"uuid": "a", "p_cross_next_threshold": 0.70}],
            labels=[],
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("HISTORICAL_LABELS_UNAVAILABLE", result["reason_codes"])

    def test_real_label_metrics_are_reported_when_supplied(self):
        predictions = [
            {"uuid": "a", "p_cross_next_threshold": 0.90},
            {"uuid": "b", "p_cross_next_threshold": 0.80},
            {"uuid": "c", "p_cross_next_threshold": 0.20},
            {"uuid": "d", "p_cross_next_threshold": 0.10},
        ]
        labels = [
            {"uuid": "a", "crossed_next_threshold": "true"},
            {"uuid": "b", "crossed_next_threshold": "false"},
            {"uuid": "c", "crossed_next_threshold": "false"},
            {"uuid": "d", "crossed_next_threshold": "false"},
        ]
        result = evaluate_backtest(predictions, labels, n_bins=2)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["n"], 4)
        self.assertIsNotNone(result["brier_score"])
        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertAlmostEqual(result["recall"], 1.0)
        self.assertGreaterEqual(len(result["calibration_curve"]), 1)


if __name__ == "__main__":
    unittest.main()

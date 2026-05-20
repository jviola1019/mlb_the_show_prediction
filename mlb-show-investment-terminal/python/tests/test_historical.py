import unittest

from mlb_show_terminal.historical import evaluate_backtest


class HistoricalBacktestTests(unittest.TestCase):
    def test_missing_labels_are_unavailable(self):
        result = evaluate_backtest(
            [{"uuid": "a", "p_cross_next_threshold": 0.70}],
            labels=[],
            min_n=1,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("HISTORICAL_LABELS_UNAVAILABLE", result["reason_codes"])
        self.assertIn("accuracy", result)
        self.assertIn("confusion", result)

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
        result = evaluate_backtest(predictions, labels, n_bins=2, min_n=1)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["n"], 4)
        self.assertIsNotNone(result["brier_score"])
        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertAlmostEqual(result["recall"], 1.0)
        self.assertIn("precision_ci", result)
        self.assertIn("recall_ci", result)
        self.assertIn("expected_calibration_error", result)
        self.assertIn("confusion", result)
        self.assertGreaterEqual(len(result["calibration_curve"]), 1)

    def test_prefixed_snapshot_probability_column_is_supported(self):
        predictions = [
            {"uuid": "a", "upgrade_p_cross_next_threshold": 0.90},
            {"uuid": "b", "upgrade_p_cross_next_threshold": 0.10},
        ]
        labels = [
            {"uuid": "a", "crossed_next_threshold": "true"},
            {"uuid": "b", "crossed_next_threshold": "false"},
        ]
        result = evaluate_backtest(predictions, labels, n_bins=2, min_n=1)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["accuracy"], 1.0)

    def test_default_backtest_requires_enough_historical_labels(self):
        result = evaluate_backtest(
            [{"uuid": "a", "p_cross_next_threshold": 0.90}],
            [{"uuid": "a", "crossed_next_threshold": "true"}],
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("INSUFFICIENT_HISTORICAL_LABELS", result["reason_codes"])

    def test_single_class_labels_are_unavailable(self):
        predictions = [
            {"uuid": "a", "p_cross_next_threshold": 0.80},
            {"uuid": "b", "p_cross_next_threshold": 0.70},
        ]
        labels = [
            {"uuid": "a", "crossed_next_threshold": "true"},
            {"uuid": "b", "crossed_next_threshold": "true"},
        ]
        result = evaluate_backtest(predictions, labels, min_n=1)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("SINGLE_CLASS_HISTORICAL_LABELS", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()

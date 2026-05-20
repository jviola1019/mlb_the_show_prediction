import tempfile
import unittest
from pathlib import Path

from mlb_show_terminal.snapshots import (
    backfill_upgrade_pair,
    backtest_upgrade_files,
    build_upgrade_labels,
    listing_snapshot_row,
    score_snapshot,
    write_records_csv,
)


class SnapshotPipelineTests(unittest.TestCase):
    def test_build_upgrade_labels_detects_threshold_crossing(self):
        labels = build_upgrade_labels(
            [{"uuid": "a", "name": "A", "ovr": 84, "rarity": "Gold"}],
            [{"uuid": "a", "name": "A", "ovr": 85, "rarity": "Diamond"}],
        )
        self.assertEqual(len(labels), 1)
        self.assertTrue(labels[0]["upgraded"])
        self.assertTrue(labels[0]["crossed_next_threshold"])
        self.assertEqual(labels[0]["next_threshold"], 85)

    def test_score_snapshot_returns_flat_prediction_rows(self):
        rows = score_snapshot([
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
            }
        ])
        self.assertIn("upgrade_p_cross_next_threshold", rows[0])
        self.assertIn("flip_roi", rows[0])

    def test_historical_backfill_round_trips_scored_predictions_to_labels(self):
        pre = [
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
        post = [
            {"uuid": "a", "name": "A", "ovr": 85, "rarity": "Diamond"},
            {"uuid": "b", "name": "B", "ovr": 84, "rarity": "Gold"},
        ]
        payload = backfill_upgrade_pair(pre, post, n_bins=2, min_n=1)
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["counts"]["matched"], 2)
        self.assertEqual(payload["backtest"]["status"], "available")
        self.assertIn("expected_calibration_error", payload["backtest"])

    def test_backtest_upgrade_files_accepts_score_snapshot_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            predictions = Path(tmp) / "predictions.csv"
            labels = Path(tmp) / "labels.csv"
            write_records_csv(predictions, [
                {"uuid": "a", "upgrade_p_cross_next_threshold": 0.9},
                {"uuid": "b", "upgrade_p_cross_next_threshold": 0.1},
            ])
            write_records_csv(labels, [
                {"uuid": "a", "crossed_next_threshold": True},
                {"uuid": "b", "crossed_next_threshold": False},
            ])
            result = backtest_upgrade_files(predictions, labels, n_bins=2, min_n=1)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["n"], 2)

    def test_listing_snapshot_row_can_carry_flat_stats_for_backfill(self):
        listing = {
            "best_sell_price": 1538,
            "best_buy_price": 1120,
            "item": {
                "uuid": "a",
                "name": "A",
                "rarity": "Gold",
                "ovr": 84,
            },
        }
        row = listing_snapshot_row(
            listing,
            "pre-1",
            "2026-05-01T00:00:00Z",
            stats={
                "role": "hitter",
                "recent": {"ops": 0.950, "avg": 0.320, "plateAppearances": 42},
                "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
            },
        )
        self.assertIn("recent_ops", row)
        scored = score_snapshot([row])
        self.assertIsNotNone(scored[0]["upgrade_p_cross_next_threshold"])


if __name__ == "__main__":
    unittest.main()

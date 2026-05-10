import unittest

from mlb_show_terminal.snapshots import build_upgrade_labels, score_snapshot


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


if __name__ == "__main__":
    unittest.main()

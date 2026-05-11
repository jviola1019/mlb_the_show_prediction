import unittest

from mlb_show_terminal.upgrade import distance_to_ovr, distance_to_threshold, score_upgrade


RECENT = {"ops": 0.950, "avg": 0.320, "plateAppearances": 42}
SEASON = {"ops": 0.780, "avg": 0.270, "plateAppearances": 180}


class UpgradeThresholdTests(unittest.TestCase):
    def test_rarity_threshold_distances(self):
        self.assertEqual(distance_to_threshold(84, "gold"), 1)
        self.assertEqual(distance_to_threshold(79, "silver"), 1)
        self.assertEqual(distance_to_threshold(74, "bronze"), 1)
        self.assertEqual(distance_to_ovr(80, 85), 5)
        self.assertEqual(distance_to_ovr(75, 85), 10)

    def test_gold_84_to_85_prioritizes_over_82_to_83_shape(self):
        near = score_upgrade(
            recent=RECENT,
            season=SEASON,
            role="hitter",
            current_ovr=84,
            rarity="gold",
        )
        far = score_upgrade(
            recent=RECENT,
            season=SEASON,
            role="hitter",
            current_ovr=82,
            rarity="gold",
        )
        self.assertGreater(near.upgrade_score, far.upgrade_score)
        self.assertGreaterEqual(near.p_cross_next_threshold, far.p_cross_next_threshold)

    def test_new_rank_crossing_threshold_raises_confidence_and_reason(self):
        result = score_upgrade(
            recent={},
            season={},
            role="hitter",
            current_ovr=84,
            rarity="gold",
            new_rank=85,
        )
        self.assertEqual(result.action, "BUY SPECULATIVE")
        self.assertIn("NEW_RANK_CROSSES_THRESHOLD", result.reason_codes)
        self.assertGreaterEqual(result.p_cross_next_threshold, 0.85)

    def test_distance_to_85_is_reported_for_silver_and_gold(self):
        silver = score_upgrade(
            recent=RECENT,
            season=SEASON,
            role="hitter",
            current_ovr=79,
            rarity="silver",
        )
        gold = score_upgrade(
            recent=RECENT,
            season=SEASON,
            role="hitter",
            current_ovr=80,
            rarity="gold",
        )
        self.assertEqual(silver.distance_to_threshold, 1)
        self.assertEqual(silver.distance_to_85, 6)
        self.assertEqual(gold.distance_to_threshold, 5)
        self.assertEqual(gold.distance_to_85, 5)


if __name__ == "__main__":
    unittest.main()

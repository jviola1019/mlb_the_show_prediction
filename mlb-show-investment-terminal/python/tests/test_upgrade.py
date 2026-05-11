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

    def test_gold_80_84_targets_diamond_threshold(self):
        for ovr in range(80, 85):
            result = score_upgrade(
                recent=RECENT,
                season=SEASON,
                role="hitter",
                current_ovr=ovr,
                rarity="Gold",
            )
            self.assertEqual(result.rarity, "Gold")
            self.assertEqual(result.next_threshold, 85)

    def test_new_rank_down_never_buys(self):
        result = score_upgrade(
            recent={"ops": 1.200, "avg": 0.390, "plateAppearances": 60},
            season={"ops": 0.700, "avg": 0.240, "plateAppearances": 180},
            role="hitter",
            current_ovr=83,
            rarity="Gold",
            new_rank=82,
        )
        self.assertEqual(result.action, "SELL")
        self.assertIn("RANK_DOWN_BLOCKS_BUY", result.reason_codes)

    def test_new_rank_flat_stats_only_is_capped_at_watch(self):
        result = score_upgrade(
            recent={"era": 0.20, "whip": 0.50, "inningsPitched": 12},
            season={"era": 4.20, "whip": 1.30, "inningsPitched": 80},
            role="pitcher",
            current_ovr=83,
            rarity="Gold",
            new_rank=83,
        )
        self.assertEqual(result.action, "WATCH")
        self.assertIn("NEW_RANK_FLAT", result.reason_codes)
        self.assertIn("STATS_ONLY_SCENARIO", result.reason_codes)

    def test_probabilities_are_labeled_scenario_uncalibrated(self):
        result = score_upgrade(
            recent=RECENT,
            season=SEASON,
            role="hitter",
            current_ovr=84,
            rarity="Gold",
        )
        self.assertEqual(result.probability_kind, "scenario")
        self.assertEqual(result.model_status, "uncalibrated_threshold_model")
        self.assertIn("UNCALIBRATED_THRESHOLD_MODEL", result.reason_codes)


if __name__ == "__main__":
    unittest.main()

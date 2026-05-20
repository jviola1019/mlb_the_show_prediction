import unittest

from mlb_show_terminal.market import compute_flip
from mlb_show_terminal.strategy_matrix import (
    apply_strategy_matrix,
    build_directional_strategy,
    build_flip_strategy,
)
from mlb_show_terminal.inventory import score_inventory
from mlb_show_terminal.strategy_ontology import (
    DirectionalStrategy,
    DirectionalVerdict,
    FinalAction,
    FlipStrategy,
    FlipVerdict,
    HoldingHorizon,
    InventoryStrategy,
    InventoryVerdict,
    ValidationTier,
)


def directional(verdict: DirectionalVerdict) -> DirectionalStrategy:
    return DirectionalStrategy(
        verdict=verdict,
        investable_label="INVESTABLE" if verdict == DirectionalVerdict.BULLISH else None,
        expected_return_by_horizon={"1d": 0.01 if verdict == DirectionalVerdict.BULLISH else -0.01, "3d": None, "7d": None},
        p_up=0.6 if verdict == DirectionalVerdict.BULLISH else 0.0,
        p_down=0.4,
        p_profit=0.6 if verdict == DirectionalVerdict.BULLISH else 0.0,
        prediction_interval={"p5": None, "p50": None, "p95": None},
        quantile_forecasts={},
        forecast_cone=[],
        model_confidence=0.7,
        validation_tier=ValidationTier.SILVER,
        recommended_holding_horizon=HoldingHorizon.ONE_DAY if verdict == DirectionalVerdict.BULLISH else HoldingHorizon.MANUAL_REVIEW,
        holding_instruction="hold up to 1d unless exit/risk gate triggers first"
        if verdict == DirectionalVerdict.BULLISH
        else "do not hold as an investment",
        source_verdict=None,
    )


def flip(verdict: FlipVerdict) -> FlipStrategy:
    return FlipStrategy(
        verdict=verdict,
        raw_ask=1788,
        raw_bid=1521,
        after_tax_resale_value=1609.2,
        expected_net_stubs=88.2 if verdict != FlipVerdict.NO_FLIP_EDGE else -10,
        expected_roi_after_tax_and_friction=0.055 if verdict == FlipVerdict.FLIP_PASS else 0.0,
        p_successful_exit=0.8,
        expected_holding_time_hours=2,
        worst_case_liquidation_value=1521,
        action="instant flip only",
    )


def inventory(verdict: InventoryVerdict) -> InventoryStrategy:
    return InventoryStrategy(
        verdict=verdict,
        inventory_risk_score=0.2 if verdict != InventoryVerdict.DEAD_INVENTORY else 1.0,
        expected_exit_time_hours=2,
        liquidity_score=1,
        liquidity_recent=200,
        dead_inventory_warning=None if verdict != InventoryVerdict.DEAD_INVENTORY else "blocked",
        position_size_recommendation="normal" if verdict != InventoryVerdict.DEAD_INVENTORY else "none",
        max_position_stubs=10000 if verdict != InventoryVerdict.DEAD_INVENTORY else 0,
    )


class StrategyMatrixTests(unittest.TestCase):
    def test_matt_olson_regression_positive_spread_bearish_is_instant_flip_only(self):
        flip_result = compute_flip(1788, 1521, liquidity_score=1, liquidity_n=200, liquidity_recent=200)
        inv = score_inventory(
            liquidity_score=1,
            liquidity_recent=200,
            liquidity_n=200,
            spread_pct=flip_result.spread_pct,
        )
        f = build_flip_strategy(flip_result.to_dict(), inv)
        d = build_directional_strategy({
            "status": "ok",
            "n_prices": 200,
            "expected_ret": -0.232,
            "p_profit": 0.0,
            "p5_ret": -0.37,
            "p50_ret": -0.23,
            "p95_ret": -0.05,
            "horizons": [
                {"horizon": 1, "expected_ret": -0.2406},
                {"horizon": 3, "expected_ret": -0.2254},
                {"horizon": 7, "expected_ret": -0.2284},
            ],
            "tier": "SILVER",
            "verdict": {"status": "INVESTABLE", "failed": [], "reasons": ["legacy all gates passed"]},
        })
        c = apply_strategy_matrix(f, d, inv)

        self.assertEqual(f.verdict, FlipVerdict.FLIP_PASS)
        self.assertEqual(d.verdict, DirectionalVerdict.BEARISH)
        self.assertIsNone(d.investable_label)
        self.assertEqual(d.data_coverage_tier, ValidationTier.SILVER)
        self.assertEqual(d.performance_validation_tier, ValidationTier.SILVER)
        self.assertEqual(c.final_action, FinalAction.INSTANT_FLIP_ONLY)
        self.assertIsNone(c.investable_label)
        self.assertIn("bearish directional forecast", c.explanation)

    def test_required_matrix_rows(self):
        cases = [
            (FlipVerdict.FLIP_PASS, DirectionalVerdict.BEARISH, InventoryVerdict.HIGH_LIQUIDITY, FinalAction.INSTANT_FLIP_ONLY),
            (FlipVerdict.FLIP_PASS, DirectionalVerdict.BULLISH, InventoryVerdict.MEDIUM_LIQUIDITY, FinalAction.FLIP_OR_SHORT_HOLD),
            (FlipVerdict.FLIP_PASS, DirectionalVerdict.NEUTRAL, InventoryVerdict.HIGH_LIQUIDITY, FinalAction.SPREAD_CAPTURE_ONLY),
            (FlipVerdict.NO_FLIP_EDGE, DirectionalVerdict.BULLISH, InventoryVerdict.MEDIUM_LIQUIDITY, FinalAction.SPECULATIVE_HOLD),
            (FlipVerdict.NO_FLIP_EDGE, DirectionalVerdict.BEARISH, InventoryVerdict.THIN, FinalAction.AVOID),
            (FlipVerdict.FLIP_MARGINAL, DirectionalVerdict.BEARISH, InventoryVerdict.THIN, FinalAction.AVOID),
            (FlipVerdict.FLIP_PASS, DirectionalVerdict.BULLISH, InventoryVerdict.DEAD_INVENTORY, FinalAction.AVOID_MANUAL_REVIEW),
            (FlipVerdict.FLIP_PASS, DirectionalVerdict.INSUFFICIENT_DATA, InventoryVerdict.HIGH_LIQUIDITY, FinalAction.WATCHLIST_NO_MODEL_TRADE),
        ]
        for f, d, i, expected in cases:
            with self.subTest(f=f, d=d, i=i):
                self.assertEqual(apply_strategy_matrix(flip(f), directional(d), inventory(i)).final_action, expected)

    def test_negative_ev_blocks_directional_investable_label(self):
        d = build_directional_strategy({
            "status": "ok",
            "n_prices": 80,
            "expected_ret": -0.01,
            "p_profit": 0.0,
            "tier": "SILVER",
            "verdict": {"status": "INVESTABLE", "reasons": []},
        })
        self.assertEqual(d.verdict, DirectionalVerdict.BEARISH)
        self.assertIsNone(d.investable_label)

    def test_directional_strategy_preserves_split_validation_tiers(self):
        d = build_directional_strategy({
            "status": "ok",
            "n_prices": 120,
            "expected_ret": 0.03,
            "p_profit": 0.7,
            "data_coverage_tier": "GOLD",
            "performance_validation_tier": "BRONZE",
            "verdict": {"status": "INVESTABLE", "reasons": []},
            "horizons": [{"horizon": 1, "expected_ret": 0.03}],
        })
        self.assertEqual(d.verdict, DirectionalVerdict.BULLISH)
        self.assertEqual(d.data_coverage_tier, ValidationTier.GOLD)
        self.assertEqual(d.performance_validation_tier, ValidationTier.BRONZE)
        self.assertEqual(d.validation_tier, ValidationTier.BRONZE)


if __name__ == "__main__":
    unittest.main()

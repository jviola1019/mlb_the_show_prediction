import unittest

from mlb_show_terminal.market import compute_flip, validate_flip_formula


class MarketFlipTests(unittest.TestCase):
    def test_after_tax_profit_and_roi_formula(self):
        result = compute_flip(1538, 1120, liquidity_score=1, liquidity_n=10, liquidity_recent=4)
        self.assertAlmostEqual(result.after_tax_sale, 1538 * 0.90)
        self.assertAlmostEqual(result.profit, 1538 * 0.90 - 1120)
        self.assertAlmostEqual(result.roi, (1538 * 0.90 - 1120) / 1120)
        self.assertEqual(result.action, "BUY")

    def test_exact_formula_positive_edge(self):
        result = compute_flip(1200, 1000, liquidity_score=1, liquidity_n=10, liquidity_recent=10)
        self.assertAlmostEqual(result.after_tax_sale, 1080)
        self.assertAlmostEqual(result.profit, 80)
        self.assertAlmostEqual(result.roi, 0.08)
        self.assertEqual(result.action, "BUY")

    def test_exact_formula_negative_after_tax_edge(self):
        result = compute_flip(1000, 950, liquidity_score=1, liquidity_n=10, liquidity_recent=10)
        self.assertAlmostEqual(result.after_tax_sale, 900)
        self.assertAlmostEqual(result.profit, -50)
        self.assertAlmostEqual(result.roi, -0.05263157894736842)
        self.assertIn("NEGATIVE_AFTER_TAX_EDGE", result.reason_codes)

    def test_missing_bid_has_explicit_blockers(self):
        result = compute_flip(1000, None, liquidity_score=1)
        self.assertEqual(result.action, "NO TRADE")
        self.assertIn("MISSING_BUY_PRICE", result.reason_codes)
        self.assertIn("NON_EXECUTABLE_BOOK", result.reason_codes)

    def test_missing_ask_has_explicit_blocker(self):
        result = compute_flip(None, 1000, liquidity_score=1)
        self.assertEqual(result.action, "NO TRADE")
        self.assertIn("MISSING_SELL_PRICE", result.reason_codes)

    def test_positive_edge_below_liquidity_floor_is_no_trade(self):
        result = compute_flip(1200, 1000, liquidity_score=0.01, liquidity_n=1, liquidity_recent=1)
        self.assertEqual(result.action, "NO TRADE")
        self.assertIn("POSITIVE_AFTER_TAX_EDGE", result.reason_codes)
        self.assertIn("LIQUIDITY_BELOW_FLOOR", result.reason_codes)

    def test_positive_edge_with_liquidity_is_buy(self):
        result = compute_flip(1200, 1000, liquidity_score=0.20, liquidity_n=10, liquidity_recent=10)
        self.assertEqual(result.action, "BUY")

    def test_positive_executable_spread_is_not_negative_flip_ev(self):
        result = compute_flip(1538, 1120, liquidity_score=1, liquidity_n=10, liquidity_recent=4)
        self.assertGreater(result.profit, 0)
        self.assertGreater(result.roi, 0)
        self.assertIn("POSITIVE_AFTER_TAX_EDGE", result.reason_codes)

    def test_missing_or_zero_book_is_not_executable(self):
        missing = compute_flip(None, 1000, liquidity_score=1)
        zero = compute_flip(1000, 0, liquidity_score=1)
        self.assertFalse(missing.executable)
        self.assertEqual(missing.action, "NO TRADE")
        self.assertFalse(zero.executable)
        self.assertEqual(zero.action, "NO TRADE")

    def test_liquidity_unavailable_prevents_buy(self):
        result = compute_flip(1538, 1120)
        self.assertFalse(result.executable)
        self.assertEqual(result.action, "NO TRADE")
        self.assertIn("LIQUIDITY_UNAVAILABLE", result.reason_codes)

    def test_validation_formula_matches_engine(self):
        result = compute_flip(1538, 1120, liquidity_score=1)
        check = validate_flip_formula(1538, 1120, result)
        self.assertFalse(check["mismatch"])
        self.assertLessEqual(check["max_abs_diff"], check["tolerance"])


if __name__ == "__main__":
    unittest.main()

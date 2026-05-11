"""Tests for the 7-gate governance system (governance.py).

Mirrors R/tests/testthat/test-validation.R. One fixture per gate-fail
scenario; verdict transitions verified end-to-end.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from mlb_show_terminal.forecast import _calibration_clean, forecast_diagnostics
from mlb_show_terminal.governance import (
    ALL_GATE_KEYS,
    _coerce_dt,
    gates_summary_pills,
    gating_verdict,
    price_history_records,
    validation_gates,
)


VALID_UUID = "a" * 32
NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


def _ph(n: int, *, hours_old_latest: float = 1.0, start_price: float = 1200.0):
    """Build n synthetic price-history records ending hours_old_latest hours ago."""
    latest = NOW - timedelta(hours=hours_old_latest)
    out = []
    for i in range(n):
        ts = latest - timedelta(hours=(n - 1 - i))
        out.append({"timestamp": ts.isoformat(), "price": start_price + i})
    return out


def _listing(*, completed_orders_n: int = 60, valid_schema: bool = True) -> dict:
    """Build a minimal listing dict that passes / fails schema as configured."""
    item = {"uuid": VALID_UUID if valid_schema else "not-a-uuid",
            "name": "Test", "rarity": "Gold", "ovr": 84}
    return {
        "item": item,
        "best_sell_price": 1538 if valid_schema else 0,
        "best_buy_price": 1120 if valid_schema else 0,
        "completed_orders": [{"price": str(1200 + (i % 7) * 4)} for i in range(completed_orders_n)],
    }


def _wfcv(*, n_trades: int = 60,
          ic_ci: list[float] | None = None,
          brier_ci: list[float] | None = None,
          ic_point: float = 0.07) -> dict:
    return {
        "status": "ok",
        "n_trades": n_trades,
        "ic_point": ic_point,
        "ic_ci": ic_ci if ic_ci is not None else [-0.05, 0.20],
        "brier_point": 0.22,
        "brier_ci": brier_ci if brier_ci is not None else [0.18, 0.26],
    }


class GateLogicTests(unittest.TestCase):
    def test_all_seven_gate_keys_present(self):
        gates = validation_gates(_ph(60), _listing(), _wfcv(), horizon=7,
                                 calibration_ok=True, now=NOW)
        for key in ALL_GATE_KEYS:
            self.assertIn(key, gates, f"missing gate key: {key}")
            self.assertIn("passed", gates[key])
            self.assertIn("reason", gates[key])

    def test_all_pass_returns_investable(self):
        gates = validation_gates(_ph(60), _listing(), _wfcv(), horizon=7,
                                 calibration_ok=True, now=NOW)
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "INVESTABLE")
        self.assertEqual(verdict["failed"], [])
        self.assertIn("7 gates", verdict["headline"])

    def test_schema_invalid_fails_hard(self):
        gates = validation_gates(_ph(60), _listing(valid_schema=False), _wfcv(),
                                 horizon=7, calibration_ok=True, now=NOW)
        self.assertFalse(gates["schema_valid"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "NOT INVESTABLE")
        self.assertIn("schema_valid", verdict["failed"])

    def test_insufficient_history_fails_hard(self):
        gates = validation_gates(_ph(10), _listing(), _wfcv(), horizon=7,
                                 calibration_ok=True, now=NOW)
        self.assertFalse(gates["history_sufficient"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "NOT INVESTABLE")
        self.assertIn("history_sufficient", verdict["failed"])

    def test_stale_data_fails_hard(self):
        # 72h old > 48h freshness cap
        gates = validation_gates(_ph(60, hours_old_latest=72.0), _listing(),
                                 _wfcv(), horizon=7, calibration_ok=True, now=NOW)
        self.assertFalse(gates["data_fresh"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "NOT INVESTABLE")
        self.assertIn("data_fresh", verdict["failed"])

    def test_too_few_cv_trades_fails_hard(self):
        gates = validation_gates(_ph(60), _listing(), _wfcv(n_trades=15),
                                 horizon=7, calibration_ok=True, now=NOW)
        self.assertFalse(gates["cv_available"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "NOT INVESTABLE")

    def test_negative_skill_soft_fails_observational(self):
        # IC upper-CI < 0 means CV demonstrates significant anti-skill
        gates = validation_gates(_ph(60), _listing(),
                                 _wfcv(ic_ci=[-0.30, -0.10]),
                                 horizon=7, calibration_ok=True, now=NOW)
        self.assertFalse(gates["cv_skill_not_negative_sig"]["passed"])
        # Hard gates all pass:
        for k in ("schema_valid", "history_sufficient", "data_fresh", "cv_available"):
            self.assertTrue(gates[k]["passed"], f"expected hard gate {k} to pass")
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "OBSERVATIONAL ONLY")
        self.assertIn("cv_skill_not_negative_sig", verdict["failed"])

    def test_wide_ci_soft_fails_observational(self):
        gates = validation_gates(_ph(60), _listing(),
                                 _wfcv(brier_ci=[0.10, 0.45]),  # width 0.35 > 0.20
                                 horizon=7, calibration_ok=True, now=NOW)
        self.assertFalse(gates["ci_width_acceptable"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "OBSERVATIONAL ONLY")
        self.assertIn("ci_width_acceptable", verdict["failed"])

    def test_calibration_absent_soft_fails_observational(self):
        gates = validation_gates(_ph(60), _listing(), _wfcv(),
                                 horizon=7, calibration_ok=False, now=NOW)
        self.assertFalse(gates["calibration_present"]["passed"])
        verdict = gating_verdict(gates)
        self.assertEqual(verdict["status"], "OBSERVATIONAL ONLY")
        self.assertIn("calibration_present", verdict["failed"])

    def test_pills_one_per_gate(self):
        gates = validation_gates(_ph(60), _listing(), _wfcv(), horizon=7,
                                 calibration_ok=True, now=NOW)
        pills = gates_summary_pills(gates)
        self.assertEqual(len(pills), len(ALL_GATE_KEYS))
        for pill in pills:
            self.assertIn(pill["tone"], ("bull", "bear"))
            self.assertIn(pill["key"], ALL_GATE_KEYS)


class ForecastDiagnosticsIntegrationTests(unittest.TestCase):
    """End-to-end: forecast_diagnostics produces a verdict via governance."""

    def _good_listing(self, n_orders: int = 80) -> dict:
        latest = NOW - timedelta(hours=1)
        orders = []
        for i in range(n_orders):
            ts = latest - timedelta(hours=(n_orders - 1 - i))
            orders.append({"date": ts.isoformat(), "price": str(1200 + (i % 9) * 5)})
        return {
            "item": {"uuid": VALID_UUID, "name": "Fixture", "rarity": "Gold", "ovr": 84},
            "best_sell_price": 1538,
            "best_buy_price": 1120,
            "completed_orders": orders,
        }

    def test_forecast_returns_verdict_block(self):
        out = forecast_diagnostics(self._good_listing())
        self.assertIn("verdict", out)
        self.assertIn(out["verdict"]["status"],
                      ("INVESTABLE", "OBSERVATIONAL ONLY", "NOT INVESTABLE"))
        self.assertIn("gates", out)
        for key in ALL_GATE_KEYS:
            self.assertIn(key, out["gates"])

    def test_tax_rate_threaded_through_returns(self):
        # Tighter tax (lower tax_rate) should produce higher expected returns
        low_tax = forecast_diagnostics(self._good_listing(), tax_rate=0.05)
        high_tax = forecast_diagnostics(self._good_listing(), tax_rate=0.15)
        if low_tax.get("status") == "ok" and high_tax.get("status") == "ok":
            self.assertGreater(low_tax["expected_ret"], high_tax["expected_ret"])
        # And tax_rate should be surfaced
        self.assertIn("tax_rate", low_tax)
        self.assertEqual(low_tax["tax_rate"], 0.05)

    def test_short_listing_returns_not_investable(self):
        out = forecast_diagnostics({
            "item": {"uuid": VALID_UUID},
            "best_sell_price": 1000,
            "best_buy_price": 800,
            "completed_orders": [{"price": "1000"}, {"price": "1010"}],
        })
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["verdict"]["status"], "NOT INVESTABLE")


class PriceHistoryRecordsTests(unittest.TestCase):
    def test_completed_orders_with_timestamps(self):
        listing = {
            "completed_orders": [
                {"date": "2026-05-10T10:00:00Z", "price": "1200"},
                {"date": "2026-05-10T11:00:00Z", "price": "1210"},
            ],
        }
        records = price_history_records(listing)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["price"], 1200.0)

    def test_completed_orders_without_timestamps_returns_empty(self):
        listing = {"completed_orders": [{"price": "1200"} for _ in range(60)]}
        # No timestamps -> no records (governance can't validate freshness)
        records = price_history_records(listing)
        self.assertEqual(records, [])

    def test_completed_orders_with_the_show_native_format(self):
        # The actual format returned by mlb26.theshow.com/apis/listing.json:
        # "MM/DD/YYYY HH:MM:SS" (no timezone). This was the production-blocking
        # bug that caused every real card to fail data_fresh + history_sufficient.
        listing = {
            "completed_orders": [
                {"date": "05/10/2026 10:00:00", "price": "1200"},
                {"date": "05/10/2026 11:00:00", "price": "1,210"},  # comma in price
            ],
        }
        records = price_history_records(listing)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["price"], 1210.0)


class DateParserRegressionTests(unittest.TestCase):
    """The Show returns timestamps as 'MM/DD/YYYY HH:MM:SS'; the price-history
    aggregate uses 'MM/DD' (year inferred). Both must parse to UTC datetimes."""

    def test_the_show_completed_orders_format(self):
        dt = _coerce_dt("05/10/2026 23:29:54")
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 23)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_short_price_history_format(self):
        dt = _coerce_dt("05/10", default_year=2026)
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 5)
        self.assertEqual(dt.day, 10)

    def test_iso_format_with_z_suffix(self):
        dt = _coerce_dt("2026-05-10T23:29:54Z")
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_garbage_string_returns_none(self):
        self.assertIsNone(_coerce_dt("not-a-date"))


class CalibrationCleanTests(unittest.TestCase):
    """Real card walk-forward predictions cluster around 0.5. Gate 7 must
    grade the densest reliability bin locally, not require all bins populated."""

    def test_single_well_calibrated_bin_passes(self):
        bins = [{"bin_lo": 0.4, "bin_hi": 0.6, "n": 80,
                 "mean_pred": 0.501, "observed_rate": 0.512}]
        result = _calibration_clean({"status": "ok", "bins": bins})
        self.assertTrue(result["ok"], result.get("reason"))

    def test_miscalibrated_dense_bin_fails(self):
        bins = [{"bin_lo": 0.4, "bin_hi": 0.6, "n": 80,
                 "mean_pred": 0.50, "observed_rate": 0.85}]  # 35-point miss
        result = _calibration_clean({"status": "ok", "bins": bins})
        self.assertFalse(result["ok"])
        self.assertIn("calibration miss", result["reason"])

    def test_undersized_bin_fails(self):
        bins = [{"bin_lo": 0.4, "bin_hi": 0.6, "n": 10,
                 "mean_pred": 0.50, "observed_rate": 0.50}]
        result = _calibration_clean({"status": "ok", "bins": bins})
        self.assertFalse(result["ok"])
        self.assertIn(">=25", result["reason"])

    def test_status_unavailable_fails(self):
        result = _calibration_clean({"status": "unavailable", "bins": []})
        self.assertFalse(result["ok"])

    def test_picks_densest_bin_not_first(self):
        bins = [
            {"bin_lo": 0.0, "bin_hi": 0.2, "n": 1,
             "mean_pred": 0.10, "observed_rate": 0.90},  # miscalibrated but tiny
            {"bin_lo": 0.4, "bin_hi": 0.6, "n": 80,
             "mean_pred": 0.50, "observed_rate": 0.51},
        ]
        result = _calibration_clean({"status": "ok", "bins": bins})
        self.assertTrue(result["ok"], result.get("reason"))


if __name__ == "__main__":
    unittest.main()

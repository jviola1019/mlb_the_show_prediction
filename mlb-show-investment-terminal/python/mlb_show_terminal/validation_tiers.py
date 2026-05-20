"""Validation tier helpers.

Coverage and performance are intentionally separate. A large retained history
can make a backtest data-rich while still proving that a strategy loses stubs
after tax. In that case the coverage tier may rise, but the performance tier
must not.
"""

from __future__ import annotations

import math
from typing import Any


def data_coverage_tier(sample_size: int | float | None) -> str:
    """Return a sample-size-only tier for real historical coverage."""

    n = _num(sample_size) or 0.0
    if n < 30:
        return "UNVALIDATED"
    if n < 100:
        return "BRONZE"
    if n < 500:
        return "SILVER"
    if n < 2000:
        return "GOLD"
    return "PLATINUM"


def validation_summary(
    metrics: dict[str, Any] | None,
    baselines: dict[str, Any] | None,
    *,
    sample_size: int | float | None,
    trades_taken: int | float | None,
    calibration_status: str = "unavailable",
) -> dict[str, Any]:
    """Build conservative validation fields for a backtest result.

    ``performance_validation_tier`` remains UNVALIDATED/BRONZE unless there is
    positive after-tax PnL, enough trades, baseline outperformance, and an
    available calibration audit. This prevents sample depth from being confused
    with profitable model skill.
    """

    metrics = metrics or {}
    baselines = baselines or {}
    coverage = data_coverage_tier(sample_size)
    n_trades = int(_num(trades_taken) or 0)
    total_stubs = _num(metrics.get("total_stubs")) or 0.0
    hit_rate = _num(metrics.get("hit_rate"))
    profit_factor = _num(metrics.get("profit_factor"))
    baseline_totals = {
        name: total
        for name, total in ((name, _baseline_total(payload)) for name, payload in baselines.items())
        if total is not None
    }
    comparable = {name: total for name, total in baseline_totals.items() if name != "no_trade"}
    beats_no_trade = total_stubs > (baseline_totals.get("no_trade") or 0.0)
    beats_comparable = all(total_stubs > total for total in comparable.values()) if comparable else False
    positive_distribution = (hit_rate is not None and hit_rate > 0.5) or (
        profit_factor is not None and profit_factor > 1.0
    )
    calibrated = calibration_status == "available"

    blockers: list[str] = []
    if n_trades <= 0:
        blockers.append("NO_TRADES_TAKEN")
    if total_stubs <= 0:
        blockers.append("NON_POSITIVE_AFTER_TAX_PNL")
    if not beats_no_trade:
        blockers.append("DOES_NOT_BEAT_NO_TRADE")
    if comparable and not beats_comparable:
        blockers.append("DOES_NOT_BEAT_NAIVE_BASELINES")
    if not positive_distribution:
        blockers.append("WEAK_OR_UNKNOWN_RETURN_DISTRIBUTION")
    if not calibrated:
        blockers.append("CALIBRATION_AUDIT_UNAVAILABLE")

    if n_trades <= 0:
        performance = "UNVALIDATED"
        verdict = "INSUFFICIENT DATA"
    elif total_stubs <= 0 or not beats_no_trade:
        performance = "BRONZE"
        verdict = "FAIL"
    elif blockers:
        performance = "BRONZE"
        verdict = "LIMITED"
    else:
        performance = _promoted_performance_tier(coverage, n_trades)
        verdict = "PASS"

    return {
        "data_coverage_tier": coverage,
        "performance_validation_tier": performance,
        "validation_tier": performance,
        "validation_verdict": verdict,
        "calibration_status": calibration_status,
        "baseline_comparison": {
            "model_total_stubs": total_stubs,
            "baseline_total_stubs": baseline_totals,
            "beats_no_trade": beats_no_trade,
            "beats_comparable_baselines": beats_comparable,
            "promotion_blockers": blockers,
        },
    }


def unavailable_validation_summary(reason: str = "INSUFFICIENT_REAL_HISTORY") -> dict[str, Any]:
    return {
        "data_coverage_tier": "UNVALIDATED",
        "performance_validation_tier": "UNVALIDATED",
        "validation_tier": "UNVALIDATED",
        "validation_verdict": "INSUFFICIENT DATA",
        "calibration_status": "unavailable",
        "baseline_comparison": {
            "model_total_stubs": 0.0,
            "baseline_total_stubs": {},
            "beats_no_trade": False,
            "beats_comparable_baselines": False,
            "promotion_blockers": [reason],
        },
    }


def _promoted_performance_tier(coverage: str, trades_taken: int) -> str:
    if coverage in {"PLATINUM", "GOLD"} and trades_taken >= 500:
        return "GOLD"
    if coverage in {"PLATINUM", "GOLD", "SILVER"} and trades_taken >= 100:
        return "SILVER"
    return "BRONZE"


def _baseline_total(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    direct = _num(payload.get("total_stubs"))
    if direct is not None:
        return direct
    nested = [_baseline_total(value) for value in payload.values() if isinstance(value, dict)]
    nested = [value for value in nested if value is not None]
    if nested:
        return sum(nested)
    return None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

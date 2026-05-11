"""Statistical validation gates for the investment terminal.

Ported from R/quant_validation.R. The CARD tab must never publish an action
verb (BUY/SELL/etc.) when the underlying analysis cannot support it. These
gates encode the minimum bar — any failed gate downgrades or suppresses the
recommendation.

Seven gates, in order of severity:
  1. schema_valid              - listing has required fields and a valid UUID.
  2. history_sufficient        - enough price points for a stable bootstrap.
  3. data_fresh                - most recent tick within 48h.
  4. cv_available              - walk-forward CV produced >= 30 trades.
  5. cv_skill_not_negative_sig - CV IC upper-CI bound >= 0 (no sig anti-skill).
  6. ci_width_acceptable       - Brier CI width <= 0.20 AND IC CI width <= 0.50.
  7. calibration_present       - isotonic / reliability binning produced finite,
                                 usable bins (proxy for held-out calibration).

Verdict tiers:
  - INVESTABLE         - all 7 gates pass; full recommendation shown.
  - OBSERVATIONAL ONLY - gates 1-4 pass; 5, 6, or 7 fails. Direction shown,
                         action verb suppressed, no Kelly sizing.
  - NOT INVESTABLE     - any of gates 1-4 fails. ABSTAIN verdict; EV table
                         blanked entirely.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

HARD_GATE_KEYS = (
    "schema_valid",
    "history_sufficient",
    "data_fresh",
    "cv_available",
)
SOFT_GATE_KEYS = (
    "cv_skill_not_negative_sig",
    "ci_width_acceptable",
    "calibration_present",
)
ALL_GATE_KEYS = HARD_GATE_KEYS + SOFT_GATE_KEYS

_UUID_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _is_valid_uuid(value: Any) -> bool:
    return isinstance(value, str) and bool(_UUID_RE.match(value))


def _gate(passed: bool, reason: str = "ok") -> dict[str, Any]:
    return {"passed": bool(passed), "reason": "ok" if passed else reason}


_DATETIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S",  # The Show completed_orders: "05/10/2026 23:26:58"
    "%m/%d/%Y %I:%M:%S %p",  # "05/10/2026 11:26:58 PM" variant
    "%m/%d/%Y",  # date-only fallback
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def _coerce_dt(value: Any, *, default_year: int | None = None) -> datetime | None:
    """Parse a timestamp from the heterogeneous shapes returned by The Show.

    Handles:
    - ISO 8601 (`2026-05-10T23:26:58Z`, `2026-05-10T23:26:58+00:00`)
    - The Show completed_orders (`05/10/2026 23:26:58`)
    - The Show price_history daily aggregate (`05/10`) — year inferred from
      ``default_year`` (or current year if None).
    - Unix timestamps (int/float seconds)
    - Native datetime
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None

    # ISO 8601 (with optional trailing Z)
    iso_s = s[:-1] + "+00:00" if s.endswith("Z") else s
    try:
        parsed = datetime.fromisoformat(iso_s)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # The Show short price-history format "MM/DD" - inject year
    if len(s) <= 5 and "/" in s and s.count("/") == 1:
        year = default_year if default_year is not None else datetime.now(timezone.utc).year
        try:
            parsed = datetime.strptime(f"{s}/{year}", "%m/%d/%Y")
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    # The Show long format with optional time
    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _latest_timestamp(price_history: Any) -> datetime | None:
    if not isinstance(price_history, list):
        return None
    candidates: list[datetime] = []
    for row in price_history:
        if not isinstance(row, dict):
            continue
        dt = _coerce_dt(row.get("timestamp") or row.get("date") or row.get("time"))
        if dt is not None:
            candidates.append(dt)
    return max(candidates) if candidates else None


def _ci_width(ci: Any) -> float | None:
    if isinstance(ci, list) and len(ci) == 2:
        lo, hi = ci
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            if math.isfinite(lo) and math.isfinite(hi):
                return float(hi - lo)
    return None


def _ic_upper(ci: Any) -> float | None:
    if isinstance(ci, list) and len(ci) == 2:
        hi = ci[1]
        if isinstance(hi, (int, float)) and math.isfinite(hi):
            return float(hi)
    return None


def _calibration_ok(calibration_ok: Any) -> tuple[bool, str]:
    """Accept a bare bool or a dict like ``{"ok": bool, "reason": str}``."""
    if isinstance(calibration_ok, dict):
        ok = bool(calibration_ok.get("ok"))
        reason = calibration_ok.get("reason") or (
            "ok" if ok else "isotonic calibration did not improve held-out Brier"
        )
        return ok, str(reason)
    ok = bool(calibration_ok)
    reason = "ok" if ok else "isotonic calibration unavailable or did not improve held-out Brier"
    return ok, reason


def validation_gates(
    price_history: Any,
    listing: dict[str, Any] | None,
    wfcv: dict[str, Any] | None,
    *,
    horizon: int = 7,
    calibration_ok: Any = True,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute the seven gates. Mirrors R/quant_validation.R::validation_gates()."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # ---- Gate 1: schema ----
    item = (listing or {}).get("item") or {}
    schema_ok = (
        listing is not None
        and isinstance(item, dict)
        and _is_valid_uuid(item.get("uuid"))
        and isinstance((listing or {}).get("best_sell_price"), (int, float))
        and (listing or {}).get("best_sell_price", 0) > 0
        and isinstance((listing or {}).get("best_buy_price"), (int, float))
        and (listing or {}).get("best_buy_price", 0) > 0
        and isinstance((listing or {}).get("completed_orders"), list)
        and len((listing or {}).get("completed_orders") or []) >= 8
    )
    schema_reason = "listing missing required fields or completed_orders < 8"

    # ---- Gate 2: history sufficient ----
    if isinstance(price_history, list):
        hist_n = len(price_history)
    else:
        hist_n = 0
    needed = max(50, 6 * int(horizon))
    hist_ok = hist_n >= needed
    hist_reason = (
        f"only {hist_n} price points (need {needed} for horizon={horizon})"
    )

    # ---- Gate 3: data freshness ----
    latest = _latest_timestamp(price_history)
    if latest is None:
        fresh_ok = False
        fresh_reason = "no price history"
    else:
        age_h = (now - latest).total_seconds() / 3600.0
        fresh_ok = math.isfinite(age_h) and age_h <= 48.0
        fresh_reason = f"most recent tick is {age_h:.1f}h old (>48h)"

    # ---- Gate 4: CV availability ----
    cv_n = int((wfcv or {}).get("n_trades") or 0)
    cv_ok = wfcv is not None and cv_n >= 30
    cv_reason = f"walk-forward CV unavailable or n_trades={cv_n} (<30)"

    # ---- Gate 5: skill not significantly negative ----
    ic_ci = (wfcv or {}).get("ic_ci")
    ic_upper = _ic_upper(ic_ci)
    if ic_upper is not None:
        skill_ok = ic_upper >= 0
        skill_reason = (
            f"CV IC upper bound = {ic_upper:+.2f} (significant negative skill)"
        )
    elif not cv_ok:
        skill_ok = False
        skill_reason = "CV unavailable; cannot evaluate skill"
    else:
        skill_ok = True
        skill_reason = "ok"

    # ---- Gate 6: CI width acceptable ----
    brier_w = _ci_width((wfcv or {}).get("brier_ci"))
    ic_w = _ci_width((wfcv or {}).get("ic_ci"))
    if wfcv is None or not cv_ok:
        width_ok = False
        width_reason = "CV unavailable; cannot evaluate CI width"
    else:
        width_ok = (
            brier_w is not None
            and ic_w is not None
            and brier_w <= 0.20
            and ic_w <= 0.50
        )
        width_reason = (
            f"CI too wide (Brier width={brier_w if brier_w is not None else float('nan'):.2f}, "
            f"IC width={ic_w if ic_w is not None else float('nan'):.2f}; cap 0.20/0.50)"
        )

    # ---- Gate 7: calibration present ----
    cal_ok, cal_reason = _calibration_ok(calibration_ok)

    return {
        "schema_valid": _gate(schema_ok, schema_reason),
        "history_sufficient": _gate(hist_ok, hist_reason),
        "data_fresh": _gate(fresh_ok, fresh_reason),
        "cv_available": _gate(cv_ok, cv_reason),
        "cv_skill_not_negative_sig": _gate(skill_ok, skill_reason),
        "ci_width_acceptable": _gate(width_ok, width_reason),
        "calibration_present": _gate(cal_ok, cal_reason),
    }


def gating_verdict(gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Map gate results to a verdict. Mirrors R/quant_validation.R::gating_verdict()."""
    hard_pass = all(gates.get(k, {}).get("passed") for k in HARD_GATE_KEYS)
    soft_keys_present = [k for k in SOFT_GATE_KEYS if k in gates]
    soft_pass = all(gates[k]["passed"] for k in soft_keys_present)

    failed = [k for k in ALL_GATE_KEYS if k in gates and not gates[k]["passed"]]
    reasons = [gates[k]["reason"] for k in failed]
    failed_csv = ",".join(failed)

    if not hard_pass:
        return {
            "status": "NOT INVESTABLE",
            "badge_tone": "bear",
            "headline": "ABSTAIN - INSUFFICIENT VALIDATION",
            "reasons": reasons,
            "failed": failed,
            "failed_csv": failed_csv,
        }
    if not soft_pass:
        return {
            "status": "OBSERVATIONAL ONLY",
            "badge_tone": "warn",
            "headline": "OBSERVATIONAL ONLY - direction reported, no action",
            "reasons": reasons,
            "failed": failed,
            "failed_csv": failed_csv,
        }
    return {
        "status": "INVESTABLE",
        "badge_tone": "bull",
        "headline": "INVESTABLE - all 7 gates passed",
        "reasons": [],
        "failed": [],
        "failed_csv": "",
    }


_GATE_SHORT_NAMES = {
    "schema_valid": "SCHEMA",
    "history_sufficient": "HISTORY",
    "data_fresh": "FRESHNESS",
    "cv_available": "CV AVAILABLE",
    "cv_skill_not_negative_sig": "CV SKILL",
    "ci_width_acceptable": "CI WIDTH",
    "calibration_present": "CALIBRATION",
}


def gates_summary_pills(gates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact pill representation suitable for the React UI."""
    pills: list[dict[str, Any]] = []
    for key in ALL_GATE_KEYS:
        if key not in gates:
            continue
        g = gates[key]
        passed = bool(g.get("passed"))
        pills.append(
            {
                "key": key,
                "label": _GATE_SHORT_NAMES.get(key, key.upper()),
                "tone": "bull" if passed else "bear",
                "mark": "OK" if passed else "FAIL",
                "passed": passed,
                "reason": "" if passed else (g.get("reason") or ""),
            }
        )
    return pills


def price_history_records(listing: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract a normalized [{timestamp, price}] list from a listing payload.

    Accepts both `completed_orders` (preferred, has per-order timestamps and
    prices) and `price_history` (fallback aggregate). Used by validation_gates
    to evaluate freshness and sufficiency without re-reading the listing.
    """
    out: list[dict[str, Any]] = []
    orders = listing.get("completed_orders") or []
    if isinstance(orders, list):
        for row in orders:
            if not isinstance(row, dict):
                continue
            ts = _coerce_dt(row.get("date") or row.get("timestamp"))
            price_raw = row.get("price")
            try:
                price = float(str(price_raw).replace(",", "")) if price_raw is not None else None
            except (TypeError, ValueError):
                price = None
            if ts is not None and price is not None and price > 0:
                out.append({"timestamp": ts.isoformat(), "price": price})
    if out:
        return out

    history = listing.get("price_history") or (listing.get("item") or {}).get("price_history") or []
    if isinstance(history, list):
        for row in history:
            if not isinstance(row, dict):
                continue
            ts = _coerce_dt(row.get("date") or row.get("timestamp"))
            ask = row.get("best_sell_price")
            bid = row.get("best_buy_price")
            try:
                ask_n = float(ask) if ask not in (None, "") else None
                bid_n = float(bid) if bid not in (None, "") else None
            except (TypeError, ValueError):
                ask_n, bid_n = None, None
            vals = [v for v in (ask_n, bid_n) if v is not None and v > 0]
            if ts is not None and vals:
                out.append({"timestamp": ts.isoformat(), "price": sum(vals) / len(vals)})
    return out

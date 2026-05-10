"""Executable market microstructure math.

The flip engine intentionally ignores time-series forecasts. It only evaluates
whether the current bid/ask book can support an executable after-tax stub flip.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if isfinite(out) else None


def _csv(values: list[str]) -> str:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return ",".join(seen)


@dataclass(frozen=True)
class FlipResult:
    sell_price: float | None
    buy_price: float | None
    after_tax_sale: float | None
    profit: float | None
    roi: float | None
    spread_pct: float | None
    liquidity_score: float | None
    liquidity_n: int
    liquidity_recent: int | None
    executable: bool
    action: str
    reason_codes: list[str]
    reason_codes_csv: str
    failed_gates: list[str]
    failed_gates_csv: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_flip(
    sell_price: Any,
    buy_price: Any,
    *,
    liquidity_score: Any = None,
    liquidity_n: Any = 0,
    liquidity_recent: Any = None,
    tax_rate: float = 0.10,
    min_roi: float = 0.01,
    min_liquidity_score: float = 0.05,
) -> FlipResult:
    ask = _num(sell_price)
    bid = _num(buy_price)
    liq_score = _num(liquidity_score)
    liq_n = int(_num(liquidity_n) or 0)
    liq_recent_raw = _num(liquidity_recent)
    liq_recent = int(liq_recent_raw) if liq_recent_raw is not None else None

    reasons: list[str] = []
    failed: list[str] = []

    if ask is None or ask <= 0:
        reasons.append("MISSING_SELL_PRICE")
        failed.append("sell_price")
    if bid is None or bid <= 0:
        reasons.append("MISSING_BUY_PRICE")
        failed.append("buy_price")

    executable_prices = ask is not None and ask > 0 and bid is not None and bid > 0
    after_tax_sale = ask * (1 - tax_rate) if ask is not None and ask > 0 else None
    profit = after_tax_sale - bid if executable_prices and after_tax_sale is not None else None
    roi = profit / bid if profit is not None and bid and bid > 0 else None
    spread_pct = (ask - bid) / ask if executable_prices and ask else None

    if not executable_prices:
        reasons.append("NON_EXECUTABLE_BOOK")
    if spread_pct is None:
        reasons.append("SPREAD_UNAVAILABLE")
        failed.append("spread")

    liquidity_available = liq_score is not None and liq_score >= min_liquidity_score
    if liq_score is None:
        reasons.append("LIQUIDITY_UNAVAILABLE")
        failed.append("liquidity")
    elif liq_score < min_liquidity_score:
        reasons.append("LIQUIDITY_BELOW_FLOOR")
        failed.append("liquidity")

    if profit is not None and profit > 0:
        reasons.append("POSITIVE_AFTER_TAX_EDGE")
    elif profit is not None and profit < 0:
        reasons.append("NEGATIVE_AFTER_TAX_EDGE")
    elif profit is not None:
        reasons.append("BREAKEVEN_AFTER_TAX")

    if roi is not None and roi < min_roi:
        reasons.append("ROI_BELOW_FLOOR")
        failed.append("roi")

    executable = executable_prices and spread_pct is not None and liquidity_available
    if not executable:
        action = "NO TRADE"
    elif roi is not None and roi >= min_roi and profit is not None and profit > 0:
        action = "BUY"
    elif roi is not None and roi <= -0.05:
        action = "SELL"
    else:
        action = "HOLD"

    unique_reasons = list(dict.fromkeys(reasons))
    unique_failed = list(dict.fromkeys(failed))
    return FlipResult(
        sell_price=ask,
        buy_price=bid,
        after_tax_sale=after_tax_sale,
        profit=profit,
        roi=roi,
        spread_pct=spread_pct,
        liquidity_score=liq_score,
        liquidity_n=liq_n,
        liquidity_recent=liq_recent,
        executable=executable,
        action=action,
        reason_codes=unique_reasons,
        reason_codes_csv=_csv(unique_reasons),
        failed_gates=unique_failed,
        failed_gates_csv=_csv(unique_failed),
    )


def validate_flip_formula(
    sell_price: Any,
    buy_price: Any,
    engine: FlipResult | dict[str, Any] | None = None,
    *,
    tolerance: float = 1e-6,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    ask = _num(sell_price)
    bid = _num(buy_price)
    if engine is None:
        engine = compute_flip(
            ask,
            bid,
            liquidity_score=1,
            liquidity_n=1,
            liquidity_recent=1,
            min_liquidity_score=0,
            tax_rate=tax_rate,
        )
    engine_dict = engine.to_dict() if isinstance(engine, FlipResult) else engine
    manual_after_tax = ask * (1 - tax_rate) if ask is not None and ask > 0 else None
    manual_profit = (
        manual_after_tax - bid
        if manual_after_tax is not None and bid is not None and bid > 0
        else None
    )
    manual_roi = manual_profit / bid if manual_profit is not None and bid else None
    diffs = [
        abs((engine_dict.get("after_tax_sale") or 0) - manual_after_tax)
        if manual_after_tax is not None
        else None,
        abs((engine_dict.get("profit") or 0) - manual_profit)
        if manual_profit is not None
        else None,
        abs((engine_dict.get("roi") or 0) - manual_roi)
        if manual_roi is not None
        else None,
    ]
    finite_diffs = [d for d in diffs if d is not None and isfinite(d)]
    max_diff = max(finite_diffs) if finite_diffs else None
    return {
        "manual_after_tax_sale": manual_after_tax,
        "manual_profit": manual_profit,
        "manual_roi": manual_roi,
        "model_after_tax_sale": engine_dict.get("after_tax_sale"),
        "model_profit": engine_dict.get("profit"),
        "model_roi": engine_dict.get("roi"),
        "max_abs_diff": max_diff,
        "tolerance": tolerance,
        "mismatch": bool(max_diff is not None and max_diff > tolerance),
    }

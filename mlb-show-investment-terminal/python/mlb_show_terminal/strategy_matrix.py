"""Deterministic strategy matrix.

This module is the only place where the final action is assigned. It applies
the exact ontology requested by the sprint: flip edge, directional forecast,
and inventory quality remain independent inputs.
"""

from __future__ import annotations

import math
from typing import Any

from .inventory import score_inventory
from .strategy_ontology import (
    CompositeStrategy,
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


RULE_VERSION = "strategy-matrix-2026-05-13"

HORIZON_HOURS = {
    HoldingHorizon.ONE_DAY: 24.0,
    HoldingHorizon.THREE_DAY: 72.0,
    HoldingHorizon.SEVEN_DAY: 168.0,
    HoldingHorizon.MANUAL_REVIEW: None,
}


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def _validation_tier(raw: Any) -> ValidationTier:
    text = str(raw or "").upper()
    if text == "PLATINUM":
        return ValidationTier.PLATINUM
    if text == "DIAMOND":
        return ValidationTier.PLATINUM
    if text == "GOLD":
        return ValidationTier.GOLD
    if text == "SILVER":
        return ValidationTier.SILVER
    if text == "BRONZE":
        return ValidationTier.BRONZE
    return ValidationTier.UNVALIDATED


def build_flip_strategy(
    flip: dict[str, Any] | None,
    inventory: InventoryStrategy,
    *,
    min_roi: float = 0.01,
    min_expected_stubs: float = 1.0,
) -> FlipStrategy:
    flip = flip or {}
    ask = _num(flip.get("sell_price"))
    bid = _num(flip.get("buy_price"))
    after_tax = _num(flip.get("after_tax_sale"))
    profit = _num(flip.get("profit"))
    roi = _num(flip.get("roi"))
    executable = bool(flip.get("executable"))
    spread_pct = _num(flip.get("spread_pct"))
    reasons = list(flip.get("reason_codes") or [])
    failed = list(flip.get("failed_gates") or [])
    passed: list[str] = []

    if after_tax is not None and bid is not None and after_tax > bid:
        passed.append("spread")
    else:
        failed.append("spread")

    if roi is not None and roi >= min_roi:
        passed.append("roi")
    else:
        failed.append("roi")

    if profit is not None and profit >= min_expected_stubs:
        passed.append("expected_stubs")
    else:
        failed.append("expected_stubs")

    if inventory.verdict in {InventoryVerdict.HIGH_LIQUIDITY, InventoryVerdict.MEDIUM_LIQUIDITY}:
        passed.append("liquidity")
    else:
        failed.append("liquidity")

    if inventory.verdict == InventoryVerdict.DEAD_INVENTORY:
        verdict = FlipVerdict.DO_NOT_FLIP
        action = "avoid"
        reasons.append("DEAD_INVENTORY_BLOCK")
    elif not executable or ask is None or bid is None:
        verdict = FlipVerdict.DO_NOT_FLIP
        action = "avoid"
        reasons.append("NON_EXECUTABLE_BOOK")
    elif profit is not None and profit > 0 and roi is not None and roi >= min_roi and inventory.verdict in {
        InventoryVerdict.HIGH_LIQUIDITY,
        InventoryVerdict.MEDIUM_LIQUIDITY,
    }:
        verdict = FlipVerdict.FLIP_PASS
        action = "instant flip only"
        reasons.append("POSITIVE_SPREAD_AFTER_TAX_AND_FRICTION")
    elif profit is not None and profit > 0:
        verdict = FlipVerdict.FLIP_MARGINAL
        action = "watchlist"
        reasons.append("POSITIVE_BUT_MARGINAL_SPREAD")
    else:
        verdict = FlipVerdict.NO_FLIP_EDGE
        action = "avoid"
        reasons.append("NO_POSITIVE_AFTER_TAX_EDGE")

    friction_penalty = 0.0
    if inventory.verdict == InventoryVerdict.MEDIUM_LIQUIDITY:
        friction_penalty += 0.0025
    elif inventory.verdict == InventoryVerdict.THIN:
        friction_penalty += 0.01
    elif inventory.verdict == InventoryVerdict.DEAD_INVENTORY:
        friction_penalty += 0.03
    if spread_pct is not None and spread_pct > 0.25:
        friction_penalty += 0.005
    friction_roi = roi - friction_penalty if roi is not None else None

    p_exit = {
        InventoryVerdict.HIGH_LIQUIDITY: 0.92,
        InventoryVerdict.MEDIUM_LIQUIDITY: 0.74,
        InventoryVerdict.THIN: 0.42,
        InventoryVerdict.DEAD_INVENTORY: 0.0,
    }[inventory.verdict]

    return FlipStrategy(
        verdict=verdict,
        raw_ask=ask,
        raw_bid=bid,
        after_tax_resale_value=after_tax,
        expected_net_stubs=profit,
        expected_roi_after_tax_and_friction=friction_roi,
        p_successful_exit=p_exit,
        expected_holding_time_hours=inventory.expected_exit_time_hours,
        worst_case_liquidation_value=bid,
        action=action,
        reason_codes=_unique(reasons),
        gates_passed=_unique(passed),
        gates_failed=_unique(failed),
        slippage_estimate=friction_penalty,
        undercut_risk=0.01 if inventory.verdict == InventoryVerdict.HIGH_LIQUIDITY else 0.03,
        spread_compression_risk=0.02 if spread_pct and spread_pct > 0.18 else 0.01,
    )


def build_directional_strategy(forecast: dict[str, Any] | None) -> DirectionalStrategy:
    forecast = forecast or {}
    source_verdict = None
    verdict_block = forecast.get("verdict") if isinstance(forecast.get("verdict"), dict) else {}
    if isinstance(verdict_block, dict):
        source_verdict = verdict_block.get("status")
    expected_ret = _num(forecast.get("expected_ret"))
    p_profit = _num(forecast.get("p_profit"))
    p5 = _num(forecast.get("p5_ret"))
    p50 = _num(forecast.get("p50_ret"))
    p95 = _num(forecast.get("p95_ret"))
    n_prices = int(_num(forecast.get("n_prices")) or 0)
    failed = list(verdict_block.get("failed") or [])
    reasons = list(verdict_block.get("reasons") or [])
    gates = forecast.get("gates") if isinstance(forecast.get("gates"), dict) else {}
    passed = [str(k) for k, v in gates.items() if isinstance(v, dict) and v.get("passed")]
    data_coverage_tier = _validation_tier(
        forecast.get("data_coverage_tier")
        or forecast.get("coverage_tier")
        or forecast.get("tier")
    )
    performance_validation_tier = _validation_tier(
        forecast.get("performance_validation_tier")
        or forecast.get("validation_tier")
        or forecast.get("tier")
    )

    horizons: dict[str, float | None] = {"1d": None, "3d": None, "7d": expected_ret}
    for row in forecast.get("horizons") or []:
        if not isinstance(row, dict):
            continue
        h = row.get("horizon")
        er = _num(row.get("expected_ret"))
        if h in (1, 3, 7):
            horizons[f"{h}d"] = er

    if forecast.get("status") != "ok" or n_prices < 9:
        verdict = DirectionalVerdict.INSUFFICIENT_DATA
        reasons.append("INSUFFICIENT_REAL_HISTORY")
    elif source_verdict == "INVESTABLE" and expected_ret is not None and expected_ret > 0 and (p_profit or 0) > 0.5:
        verdict = DirectionalVerdict.BULLISH
        reasons.append("POSITIVE_DIRECTIONAL_EV")
    elif expected_ret is not None and (expected_ret < -0.005 or (p_profit is not None and p_profit <= 0.05)):
        verdict = DirectionalVerdict.BEARISH
        reasons.append("NEGATIVE_DIRECTIONAL_EV")
    else:
        verdict = DirectionalVerdict.NEUTRAL
        reasons.append("NO_DIRECTIONAL_EDGE")

    positive = {k: v for k, v in horizons.items() if isinstance(v, (int, float)) and v > 0}
    if verdict == DirectionalVerdict.BULLISH and positive:
        best = max(positive, key=lambda k: positive[k] or -999)
        hold = {
            "1d": HoldingHorizon.ONE_DAY,
            "3d": HoldingHorizon.THREE_DAY,
            "7d": HoldingHorizon.SEVEN_DAY,
        }[best]
        instruction = f"hold up to {hold.value} unless exit/risk gate triggers first"
        investable_label = "INVESTABLE"
    else:
        hold = HoldingHorizon.MANUAL_REVIEW
        instruction = "do not hold as an investment; use only the composite action"
        investable_label = None

    model_confidence = None
    wfcv = forecast.get("walk_forward") if isinstance(forecast.get("walk_forward"), dict) else {}
    if isinstance(wfcv, dict):
        n = _num(wfcv.get("n_trades"))
        if n is not None:
            model_confidence = max(0.0, min(1.0, n / 250.0))

    return DirectionalStrategy(
        verdict=verdict,
        investable_label=investable_label,
        expected_return_by_horizon=horizons,
        p_up=p_profit,
        p_down=1 - p_profit if p_profit is not None else None,
        p_profit=p_profit,
        prediction_interval={"p5": p5, "p50": p50, "p95": p95},
        quantile_forecasts={"p5": p5, "p25": None, "median": p50, "p75": None, "p95": p95},
        forecast_cone=list(forecast.get("cone") or []),
        model_confidence=model_confidence,
        validation_tier=performance_validation_tier,
        recommended_holding_horizon=hold,
        holding_instruction=instruction,
        source_verdict=source_verdict,
        reason_codes=_unique(reasons),
        gates_passed=_unique(passed),
        gates_failed=_unique(failed),
        data_coverage_tier=data_coverage_tier,
        performance_validation_tier=performance_validation_tier,
    )


def apply_strategy_matrix(
    flip: FlipStrategy,
    directional: DirectionalStrategy,
    inventory: InventoryStrategy,
) -> CompositeStrategy:
    f, d, i = flip.verdict, directional.verdict, inventory.verdict
    liquid = i in {InventoryVerdict.HIGH_LIQUIDITY, InventoryVerdict.MEDIUM_LIQUIDITY}

    if f == FlipVerdict.DO_NOT_FLIP and any(
        code in flip.reason_codes
        for code in ("MISSING_BUY_PRICE", "MISSING_SELL_PRICE", "NON_EXECUTABLE_BOOK")
    ):
        action = FinalAction.AVOID_MANUAL_REVIEW
        strategy_type = "manual_review"
        reason = "schema or executable-book gate failed; manual review required"
    elif d == DirectionalVerdict.INSUFFICIENT_DATA:
        action = FinalAction.WATCHLIST_NO_MODEL_TRADE
        strategy_type = "watchlist"
        reason = "insufficient real historical validation; no model trade"
    elif f == FlipVerdict.FLIP_PASS and i == InventoryVerdict.DEAD_INVENTORY:
        action = FinalAction.AVOID_MANUAL_REVIEW
        strategy_type = "manual_review"
        reason = "spread exists, but dead-inventory protection blocks entry"
    elif f == FlipVerdict.FLIP_PASS and d == DirectionalVerdict.BEARISH and liquid:
        action = FinalAction.INSTANT_FLIP_ONLY
        strategy_type = "flip"
        reason = "positive spread capture, but bearish directional forecast; do not hold as an investment"
    elif f == FlipVerdict.FLIP_PASS and d == DirectionalVerdict.BULLISH and liquid:
        action = FinalAction.FLIP_OR_SHORT_HOLD
        strategy_type = "flip_or_hold"
        reason = "spread edge and positive directional EV both clear their gates"
    elif f == FlipVerdict.FLIP_PASS and d == DirectionalVerdict.NEUTRAL and liquid:
        action = FinalAction.SPREAD_CAPTURE_ONLY
        strategy_type = "flip"
        reason = "spread edge exists, but directional forecast is neutral"
    elif f == FlipVerdict.NO_FLIP_EDGE and d == DirectionalVerdict.BULLISH and liquid:
        action = FinalAction.SPECULATIVE_HOLD
        strategy_type = "directional_hold"
        reason = "directional EV is positive, but bid/ask spread capture is not attractive"
    elif f == FlipVerdict.NO_FLIP_EDGE and d == DirectionalVerdict.BEARISH:
        action = FinalAction.AVOID
        strategy_type = "avoid"
        reason = "bearish forecast and no spread edge"
    elif f == FlipVerdict.FLIP_MARGINAL and d == DirectionalVerdict.BEARISH and i in {
        InventoryVerdict.THIN,
        InventoryVerdict.DEAD_INVENTORY,
    }:
        action = FinalAction.AVOID
        strategy_type = "avoid"
        reason = "marginal spread, bearish forecast, and weak inventory quality"
    elif i == InventoryVerdict.DEAD_INVENTORY:
        action = FinalAction.AVOID_MANUAL_REVIEW
        strategy_type = "manual_review"
        reason = "dead-inventory protection blocks model trade"
    elif f == FlipVerdict.FLIP_MARGINAL:
        action = FinalAction.MANUAL_REVIEW
        strategy_type = "manual_review"
        reason = "spread is marginal; manual review required before risking inventory"
    else:
        action = FinalAction.WATCHLIST_NO_MODEL_TRADE
        strategy_type = "watchlist"
        reason = "no deterministic strategy row promotes this card to a model trade"

    investable_label = directional.investable_label if d == DirectionalVerdict.BULLISH else None
    hold = directional.recommended_holding_horizon if investable_label else HoldingHorizon.MANUAL_REVIEW
    entry_timing, exit_timing, max_hold_hours, hold_text = _timing_instruction(
        action=action,
        flip=flip,
        directional=directional,
        inventory=inventory,
        investable_label=investable_label,
    )
    passed = _unique([f"flip:{x}" for x in flip.gates_passed] + [f"inventory:{x}" for x in inventory.gates_passed] + [f"forecast:{x}" for x in directional.gates_passed])
    failed = _unique([f"flip:{x}" for x in flip.gates_failed] + [f"inventory:{x}" for x in inventory.gates_failed] + [f"forecast:{x}" for x in directional.gates_failed])
    codes = _unique([
        flip.verdict.value.replace(" ", "_"),
        directional.verdict.value.replace(" ", "_"),
        inventory.verdict.value.replace(" ", "_"),
        action.value.replace(" ", "_").replace("/", "OR"),
        *flip.reason_codes,
        *directional.reason_codes,
        *inventory.reason_codes,
    ])
    confidence_parts = [x for x in (directional.model_confidence, flip.p_successful_exit) if x is not None]
    confidence = min(confidence_parts) if confidence_parts else None

    return CompositeStrategy(
        final_action=action,
        strategy_type=strategy_type,
        investable_label=investable_label,
        hold_duration=hold,
        holding_instruction=hold_text,
        entry_timing=entry_timing,
        exit_timing=exit_timing,
        max_hold_hours=max_hold_hours,
        explanation=reason,
        gates_passed=passed,
        gates_failed=failed,
        reason_codes=codes,
        confidence=confidence,
    )


def _timing_instruction(
    *,
    action: FinalAction,
    flip: FlipStrategy,
    directional: DirectionalStrategy,
    inventory: InventoryStrategy,
    investable_label: str | None,
) -> tuple[str, str, float | None, str]:
    exit_hours = inventory.expected_exit_time_hours or flip.expected_holding_time_hours
    if action == FinalAction.INSTANT_FLIP_ONLY:
        hours = exit_hours if exit_hours is not None else 2.0
        return (
            "enter only as a limit buy at or below current bid; skip market buys",
            f"after fill, immediately relist near current ask; cancel or liquidate if not exited within {hours:g}h",
            hours,
            f"instant flip only; target exit within {hours:g}h and do not hold as an investment",
        )
    if action == FinalAction.SPREAD_CAPTURE_ONLY:
        hours = exit_hours if exit_hours is not None else 8.0
        return (
            "enter only when after-tax spread remains positive after friction",
            f"relist immediately for spread capture; if queue does not clear within {hours:g}h, cancel and reassess",
            hours,
            f"spread capture only; target exit within {hours:g}h unless liquidity worsens first",
        )
    if action == FinalAction.FLIP_OR_SHORT_HOLD:
        horizon_hours = HORIZON_HOURS.get(directional.recommended_holding_horizon)
        hours = min(x for x in [horizon_hours, exit_hours] if x is not None) if any(
            x is not None for x in [horizon_hours, exit_hours]
        ) else None
        horizon = directional.recommended_holding_horizon.value
        return (
            "enter as limit bid only; do not chase above modeled ask/bid spread",
            f"take spread exit if filled early; otherwise hold up to {horizon} and liquidate when risk gate trips",
            hours,
            f"flip or short hold; hold up to {horizon} unless exit/risk gate triggers first",
        )
    if action == FinalAction.SPECULATIVE_HOLD and investable_label:
        horizon = directional.recommended_holding_horizon.value
        hours = HORIZON_HOURS.get(directional.recommended_holding_horizon)
        return (
            "enter only after confirming freshness, liquidity, and position-size cap",
            f"hold up to {horizon}; liquidate early if forecast turns bearish, inventory turns thin, or stop-loss/risk gate fails",
            hours,
            directional.holding_instruction,
        )
    if action in {FinalAction.AVOID, FinalAction.AVOID_MANUAL_REVIEW, FinalAction.MANUAL_REVIEW}:
        return (
            "do not enter a new model position",
            "sell existing inventory only by manual review or risk-control liquidation",
            0.0,
            "no model hold; reduce or avoid inventory",
        )
    return (
        "do not enter a model trade until required real-data gates pass",
        "watchlist only; collect fresh snapshots and reassess",
        None,
        "watchlist only; no model hold duration",
    )


def build_strategy_record(scored: dict[str, Any], listing: dict[str, Any] | None = None) -> dict[str, Any]:
    forecast = scored.get("forecast") if isinstance(scored.get("forecast"), dict) else {}
    gates = forecast.get("gates") if isinstance(forecast.get("gates"), dict) else {}
    freshness_gate = gates.get("freshness") if isinstance(gates.get("freshness"), dict) else None
    freshness_failed = bool(freshness_gate and freshness_gate.get("passed") is False)
    flip_block = scored.get("flip") if isinstance(scored.get("flip"), dict) else {}
    card = scored.get("card") if isinstance(scored.get("card"), dict) else {}
    inventory = score_inventory(
        liquidity_score=flip_block.get("liquidity_score", card.get("liquidity_score")),
        liquidity_recent=flip_block.get("liquidity_recent", card.get("liquidity_recent")),
        liquidity_n=flip_block.get("liquidity_n", card.get("liquidity_n")),
        spread_pct=flip_block.get("spread_pct", card.get("spread_pct")),
        freshness_failed=freshness_failed,
    )
    flip = build_flip_strategy(flip_block, inventory)
    directional = build_directional_strategy(forecast)
    composite = apply_strategy_matrix(flip, directional, inventory)
    return {
        "rule_version": RULE_VERSION,
        "flip": flip.to_dict(),
        "directional": directional.to_dict(),
        "inventory": inventory.to_dict(),
        "composite": composite.to_dict(),
    }

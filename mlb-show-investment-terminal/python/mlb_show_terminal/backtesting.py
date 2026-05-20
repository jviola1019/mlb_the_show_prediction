"""Real-snapshot strategy backtesting framework.

This module never fabricates market history. It evaluates only supplied
timestamped snapshots and returns an explicit insufficient-data verdict when
real observations are unavailable.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from statistics import mean, median, stdev
from typing import Any

from .validation_tiers import unavailable_validation_summary, validation_summary


TRADE_ACTIONS = {"INSTANT FLIP ONLY", "SPREAD CAPTURE ONLY", "FLIP OR SHORT HOLD", "SPECULATIVE HOLD"}
SPREAD_ACTIONS = {"INSTANT FLIP ONLY", "SPREAD CAPTURE ONLY"}


def evaluate_strategy_backtest(
    snapshots: list[dict[str, Any]],
    *,
    min_snapshots: int = 30,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    rows = [_normalize(row) for row in snapshots if isinstance(row, dict)]
    rows = [row for row in rows if row["card_uuid"] and row["timestamp"] and row["ask"] and row["bid"]]
    rows.sort(key=lambda r: (r["card_uuid"], r["timestamp"], r["raw_index"]))

    baselines = _empty_baselines()
    if len(rows) < min_snapshots:
        return {
            "status": "unavailable",
            **unavailable_validation_summary("INSUFFICIENT_REAL_MARKET_SNAPSHOTS"),
            "data_coverage_source": "INSUFFICIENT_REAL_HISTORY",
            "reason_codes": ["INSUFFICIENT_REAL_MARKET_SNAPSHOTS"],
            "required_snapshots": min_snapshots,
            "snapshots": len(rows),
            "evaluated_opportunities": 0,
            "trades_taken": 0,
            "trades_skipped": len(rows),
            "baselines": baselines,
            "metrics": _empty_metrics(),
            "sample_predictions": [],
        }

    opportunities: list[dict[str, Any]] = []
    random_ops: list[dict[str, Any]] = []
    spread_ops: list[dict[str, Any]] = []
    momentum_ops: list[dict[str, Any]] = []
    by_card: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_card.setdefault(row["card_uuid"], []).append(row)

    for card_rows in by_card.values():
        card_rows.sort(key=lambda r: (r["timestamp"], r["raw_index"]))
        for idx, row in enumerate(card_rows[:-1]):
            nxt = card_rows[idx + 1]
            action = row["final_action"]
            if action not in TRADE_ACTIONS:
                opportunities.append(
                    {
                        "taken": False,
                        "action": action,
                        "strategy_family": "no_trade",
                        "roi": 0.0,
                        "net_stubs": 0.0,
                        "hit": False,
                        "failed_exit": False,
                        "execution_assumption": "model skipped trade",
                    }
                )
            else:
                opportunities.append({**_realize_strategy(row, nxt, action=action, tax_rate=tax_rate), "taken": True, "action": action})

            spread_ops.append(
                {
                    **_realize_strategy(row, nxt, action="SPREAD CAPTURE ONLY", tax_rate=tax_rate),
                    "taken": _has_spread_edge(row, tax_rate=tax_rate),
                    "action": "NAIVE SPREAD ONLY",
                }
            )
            random_ops.append(
                {
                    **_realize_strategy(row, nxt, action="SPECULATIVE HOLD", tax_rate=tax_rate),
                    "taken": _deterministic_coin(row["card_uuid"], row["timestamp"]),
                    "action": "RANDOM TRADE",
                }
            )
            momentum_ops.append(
                {
                    **_realize_strategy(row, nxt, action="SPECULATIVE HOLD", tax_rate=tax_rate),
                    "taken": _has_positive_momentum(card_rows, idx),
                    "action": "NAIVE MOMENTUM",
                }
            )

    trades = [op for op in opportunities if op["taken"]]
    metrics = _metrics(opportunities)
    baselines["random_trade"] = _baseline_metrics(random_ops)
    baselines["naive_spread_only"] = _baseline_metrics(spread_ops)
    baselines["naive_momentum"] = _baseline_metrics(momentum_ops)
    baselines["naive_no_change_forecast"] = {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0}
    baselines["old_gate_logic"] = baselines["naive_spread_only"]
    validation = validation_summary(
        metrics,
        baselines,
        sample_size=len(rows),
        trades_taken=len(trades),
        calibration_status="unavailable",
    )

    return {
        "status": "available",
        **validation,
        "data_coverage_source": "RETAINED_MARKET_SNAPSHOTS",
        "reason_codes": [],
        "snapshots": len(rows),
        "cards": len(by_card),
        "evaluated_opportunities": len(opportunities),
        "trades_taken": len(trades),
        "trades_skipped": len(opportunities) - len(trades),
        "baselines": baselines,
        "metrics": metrics,
        "sample_predictions": opportunities[:25],
    }


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    strategy = row.get("strategy") if isinstance(row.get("strategy"), dict) else {}
    composite = strategy.get("composite") if isinstance(strategy.get("composite"), dict) else {}
    flip = strategy.get("flip") if isinstance(strategy.get("flip"), dict) else {}
    return {
        "raw_index": row.get("_index", 0),
        "card_uuid": row.get("card_uuid") or row.get("uuid") or (row.get("card") or {}).get("uuid"),
        "timestamp": str(row.get("pulled_at") or row.get("source_timestamp") or row.get("timestamp") or ""),
        "ask": _num(row.get("raw_ask") or row.get("best_sell_price") or row.get("ask")),
        "bid": _num(row.get("raw_bid") or row.get("best_buy_price") or row.get("bid")),
        "final_action": composite.get("final_action") or row.get("final_action") or row.get("decision_action") or "WATCHLIST / NO MODEL TRADE",
        "p_successful_exit": _num(flip.get("p_successful_exit")),
    }


def _empty_baselines() -> dict[str, Any]:
    return {
        "no_trade": {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0},
        "random_trade": {"status": "unavailable"},
        "naive_spread_only": {"status": "unavailable"},
        "naive_momentum": {"status": "unavailable"},
        "naive_no_change_forecast": {"status": "unavailable"},
        "old_gate_logic": {"status": "unavailable"},
    }


def _baseline_metrics(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    trades = [op for op in opportunities if op.get("taken")]
    rois = [float(op["roi"]) for op in trades]
    stubs = [float(op["net_stubs"]) for op in trades]
    return {
        "trades_taken": len(trades),
        "total_stubs": sum(stubs),
        "roi": mean(rois) if rois else None,
        "hit_rate": sum(1 for x in stubs if x > 0) / len(stubs) if stubs else None,
        "failed_exit_rate": sum(1 for op in trades if op.get("failed_exit")) / len(trades) if trades else None,
    }


def _empty_metrics() -> dict[str, Any]:
    return _metrics([])


def _metrics(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    trades = [op for op in opportunities if op.get("taken")]
    rois = [float(op["roi"]) for op in trades]
    stubs = [float(op["net_stubs"]) for op in trades]
    equity = _equity_curve(stubs)
    holding_days = [float(op["actual_holding_days"]) for op in trades if op.get("actual_holding_days") is not None]
    return {
        "average_roi": mean(rois) if rois else None,
        "median_roi": median(rois) if rois else None,
        "total_stubs": sum(stubs),
        "hit_rate": sum(1 for x in stubs if x > 0) / len(stubs) if stubs else None,
        "profit_factor": _profit_factor(stubs),
        "max_drawdown": _max_drawdown(equity),
        "sharpe_like": _ratio(rois),
        "sortino_like": _ratio([x for x in rois if x < 0]),
        "failed_exit_rate": sum(1 for op in trades if op.get("failed_exit")) / len(trades) if trades else None,
        "average_holding_time_days": mean(holding_days) if holding_days else None,
        "turnover_velocity": len(trades) / max(1, len(opportunities)),
        "inventory_aging": None,
        "stub_velocity": sum(stubs) / max(1, len(opportunities)),
        "opportunity_cost_estimate": 0.0,
    }


def _realize_strategy(row: dict[str, Any], future: dict[str, Any], *, action: str, tax_rate: float) -> dict[str, Any]:
    if action in SPREAD_ACTIONS:
        entry_price = float(row["bid"])
        exit_price = float(row["ask"])
        exit_after_tax = exit_price * (1 - tax_rate)
        exit_timestamp = row["timestamp"]
        assumption = "limit buy at current bid, relist at current ask, no queue-depth proof"
        family = "spread_capture"
    elif action == "FLIP OR SHORT HOLD":
        entry_price = float(row["bid"])
        exit_price = float(future["ask"])
        exit_after_tax = exit_price * (1 - tax_rate)
        exit_timestamp = future["timestamp"]
        assumption = "limit buy at current bid, hold to future ask, no queue-depth proof"
        family = "flip_or_short_hold"
    else:
        entry_price = float(row["ask"])
        exit_price = float(future["bid"])
        exit_after_tax = exit_price * (1 - tax_rate)
        exit_timestamp = future["timestamp"]
        assumption = "directional hold buys current ask and liquidates to future bid after tax"
        family = "directional_hold"
    net_stubs = exit_after_tax - entry_price
    entry_ts = _parse_ts(row["timestamp"])
    exit_ts = _parse_ts(exit_timestamp)
    holding_days = None
    if entry_ts is not None and exit_ts is not None:
        holding_days = max(0.0, (exit_ts - entry_ts).total_seconds() / 86400.0)
    return {
        "strategy_family": family,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_after_tax": exit_after_tax,
        "exit_timestamp": exit_timestamp,
        "actual_holding_days": holding_days,
        "net_stubs": net_stubs,
        "roi": net_stubs / entry_price if entry_price else 0.0,
        "hit": net_stubs > 0,
        "failed_exit": net_stubs <= 0,
        "fill_probability_proxy": row.get("p_successful_exit"),
        "execution_assumption": assumption,
    }


def _has_spread_edge(row: dict[str, Any], *, tax_rate: float) -> bool:
    ask, bid = row["ask"], row["bid"]
    if not ask or not bid:
        return False
    net = ask * (1 - tax_rate) - bid
    return net > 0 and net / bid >= 0.01


def _has_positive_momentum(rows: list[dict[str, Any]], idx: int) -> bool:
    if idx <= 0:
        return False
    prev = rows[idx - 1]
    cur = rows[idx]
    prev_mid = ((prev["ask"] or 0) + (prev["bid"] or 0)) / 2.0
    cur_mid = ((cur["ask"] or 0) + (cur["bid"] or 0)) / 2.0
    return prev_mid > 0 and cur_mid > prev_mid


def _deterministic_coin(card_uuid: str, timestamp: str) -> bool:
    digest = hashlib.sha256(f"{card_uuid}|{timestamp}|strategy-random-baseline-v1".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2 == 0


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _equity_curve(values: list[float]) -> list[float]:
    out: list[float] = []
    total = 0.0
    for value in values:
        total += value
        out.append(total)
    return out


def _max_drawdown(equity: list[float]) -> float | None:
    if not equity:
        return None
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        max_dd = min(max_dd, value - peak)
    return max_dd


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return None if gains == 0 else math.inf
    return gains / losses


def _ratio(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    sd = stdev(values)
    return mean(values) / sd if sd > 0 else None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

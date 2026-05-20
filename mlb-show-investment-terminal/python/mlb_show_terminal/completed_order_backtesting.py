"""Historical completed-order backtesting.

The Show listing payloads expose recent completed sales with timestamps. Those
records are real historical executions, but they are not full order-book
snapshots. This module therefore backtests directional hold decisions from
completed-sale prices only and explicitly leaves historical spread-flip
validation unavailable until real bid/ask snapshots have been collected.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from statistics import mean, median, stdev
from typing import Any, Iterable

from .governance import _coerce_dt, price_history_records
from .theshow import get_listing
from .validation_tiers import unavailable_validation_summary, validation_summary

DEFAULT_HORIZONS = (1, 3, 7)
MODEL_VERSION = "completed-order-rolling-origin-v1"
SOURCE_LIMITATIONS = [
    "completed_orders provide historical sale prices, not historical bid/ask depth",
    "spread-flip execution backtests remain unavailable from completed_orders alone",
    "labels use the first later completed sale at or after each requested horizon",
]
SNAPSHOT_SOURCE_LIMITATIONS = [
    "price_history provides daily historical best bid/ask snapshots from The Show",
    "completed_orders provide intraday sale prints but not full bid/ask depth",
    "strategy labels use only future rows after the prediction timestamp",
]


def completed_order_snapshots_from_listing(listing: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized real historical sale snapshots for one listing.

    No bid/ask values are inferred here. The only price emitted is the observed
    completed sale price or fallback aggregate price returned by
    ``price_history_records``.
    """

    item = listing.get("item") if isinstance(listing.get("item"), dict) else {}
    card_uuid = (
        item.get("uuid")
        or listing.get("uuid")
        or listing.get("card_uuid")
        or listing.get("item_uuid")
    )
    card_name = item.get("name") or listing.get("listing_name") or listing.get("name")
    records = price_history_records(listing)
    has_completed_orders = bool(listing.get("completed_orders"))
    source_type = "the_show_completed_orders" if has_completed_orders else "the_show_price_history"
    source_url = listing.get("source_url") or listing.get("_source_url")
    fetched_at = listing.get("fetched_at") or listing.get("pulled_at")

    rows: list[dict[str, Any]] = []
    for idx, rec in enumerate(records):
        timestamp = rec.get("timestamp")
        price = _num(rec.get("price"))
        if not card_uuid or not timestamp or price is None or price <= 0:
            continue
        rows.append(
            {
                "_index": idx,
                "card_uuid": str(card_uuid).lower(),
                "card_name": card_name,
                "timestamp": str(timestamp),
                "sale_price": price,
                "source_type": source_type,
                "snapshot_kind": "historical_completed_sale",
                "source_url": source_url,
                "fetched_at": fetched_at,
            }
        )
    return _dedupe_sale_snapshots(rows)


def historical_market_snapshots_from_listing(listing: dict[str, Any]) -> list[dict[str, Any]]:
    """Return real historical bid/ask snapshots from The Show price_history."""

    item = listing.get("item") if isinstance(listing.get("item"), dict) else {}
    card_uuid = (
        item.get("uuid")
        or listing.get("uuid")
        or listing.get("card_uuid")
        or listing.get("item_uuid")
    )
    card_name = item.get("name") or listing.get("listing_name") or listing.get("name")
    source_url = listing.get("source_url") or listing.get("_source_url")
    fetched_at = listing.get("fetched_at") or listing.get("pulled_at")
    history = listing.get("price_history") or item.get("price_history") or []
    rows: list[dict[str, Any]] = []
    if not isinstance(history, list):
        return rows
    for idx, row in enumerate(history):
        if not isinstance(row, dict):
            continue
        ts = _coerce_dt(row.get("date") or row.get("timestamp"))
        ask = _num(row.get("best_sell_price") or row.get("ask"))
        bid = _num(row.get("best_buy_price") or row.get("bid"))
        if not card_uuid or ts is None or ask is None or bid is None or ask <= 0 or bid <= 0:
            continue
        rows.append(
            {
                "_index": idx,
                "card_uuid": str(card_uuid).lower(),
                "card_name": card_name,
                "timestamp": ts.isoformat(),
                "raw_ask": ask,
                "raw_bid": bid,
                "mid_price": (ask + bid) / 2.0,
                "source_type": "the_show_price_history",
                "snapshot_kind": "historical_bid_ask_snapshot",
                "source_url": source_url,
                "fetched_at": fetched_at,
            }
        )
    return _dedupe_market_snapshots(rows)


def evaluate_completed_order_backtest(
    listings: Iterable[dict[str, Any]],
    *,
    min_orders: int = 30,
    lookback_orders: int = 20,
    horizons_days: Iterable[int] = DEFAULT_HORIZONS,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    """Run a deterministic rolling-origin backtest from completed sales.

    At each completed-sale row, only prior sale prices are used to create the
    directional decision. The future completed sale used as the label is found
    after the prediction timestamp, at or beyond the requested horizon.
    """

    horizons = _valid_horizons(horizons_days)
    min_orders = max(1, int(min_orders or 30))
    lookback_orders = max(2, int(lookback_orders or 20))
    tax_rate = _tax_rate(tax_rate)

    snapshots: list[dict[str, Any]] = []
    for listing in listings:
        if isinstance(listing, dict):
            snapshots.extend(completed_order_snapshots_from_listing(listing))
    snapshots = _dedupe_sale_snapshots(snapshots)

    by_card: dict[str, list[dict[str, Any]]] = {}
    for row in snapshots:
        by_card.setdefault(str(row["card_uuid"]), []).append(row)
    for rows in by_card.values():
        rows.sort(key=lambda r: (_parse_dt(r["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc), r["_index"]))

    baselines = _empty_baselines()
    if len(snapshots) < min_orders:
        return {
            "status": "unavailable",
            **unavailable_validation_summary("INSUFFICIENT_REAL_COMPLETED_ORDER_HISTORY"),
            "data_coverage_source": "INSUFFICIENT_REAL_HISTORY",
            "reason_codes": ["INSUFFICIENT_REAL_COMPLETED_ORDER_HISTORY"],
            "source": "the_show_completed_orders",
            "snapshot_kind": "historical_completed_sale",
            "source_limitations": SOURCE_LIMITATIONS,
            "model_version": MODEL_VERSION,
            "leakage_guard": _leakage_guard(lookback_orders),
            "required_orders": min_orders,
            "lookback_orders": lookback_orders,
            "horizons_days": horizons,
            "snapshots": len(snapshots),
            "cards": len(by_card),
            "evaluated_opportunities": 0,
            "trades_taken": 0,
            "trades_skipped": len(snapshots),
            "baselines": baselines,
            "horizons": {f"{h}d": _empty_metrics() for h in horizons},
            "sample_predictions": [],
        }

    opportunities_by_horizon: dict[int, list[dict[str, Any]]] = {h: [] for h in horizons}
    baseline_opportunities: dict[str, dict[int, list[dict[str, Any]]]] = {
        "random_trade": {h: [] for h in horizons},
        "naive_momentum": {h: [] for h in horizons},
    }

    for card_uuid, rows in sorted(by_card.items()):
        priced = [row for row in rows if _parse_dt(row["timestamp"]) is not None and _num(row["sale_price"]) is not None]
        if len(priced) <= lookback_orders:
            continue
        for idx in range(lookback_orders, len(priced)):
            entry = priced[idx]
            past = priced[idx - lookback_orders : idx]
            signal = _rolling_signal([float(row["sale_price"]) for row in past])
            entry_ts = _parse_dt(entry["timestamp"])
            if entry_ts is None:
                continue
            for horizon in horizons:
                future = _future_after_horizon(priced, idx, entry_ts + timedelta(days=horizon))
                if future is None:
                    continue
                realized = _realized_hold(entry, future, tax_rate=tax_rate)
                op = {
                    **realized,
                    "card_uuid": card_uuid,
                    "card_name": entry.get("card_name"),
                    "timestamp": entry["timestamp"],
                    "horizon_days": horizon,
                    "model_direction": signal["direction"],
                    "final_action": signal["final_action"],
                    "expected_return_proxy": signal["expected_return_proxy"],
                    "reason_codes": signal["reason_codes"],
                    "taken": signal["final_action"] == "SPECULATIVE HOLD",
                    "source_type": entry.get("source_type"),
                }
                opportunities_by_horizon[horizon].append(op)

                random_taken = _deterministic_coin(card_uuid, entry["timestamp"], horizon)
                baseline_opportunities["random_trade"][horizon].append({**realized, "taken": random_taken})
                baseline_opportunities["naive_momentum"][horizon].append(
                    {**realized, "taken": signal["last_return"] > 0}
                )

    horizon_metrics = {f"{h}d": _metrics(ops) for h, ops in opportunities_by_horizon.items()}
    all_ops = [op for ops in opportunities_by_horizon.values() for op in ops]
    model_trades = [op for op in all_ops if op["taken"]]
    baselines["random_trade"] = {
        f"{h}d": _metrics(ops) for h, ops in baseline_opportunities["random_trade"].items()
    }
    baselines["naive_momentum"] = {
        f"{h}d": _metrics(ops) for h, ops in baseline_opportunities["naive_momentum"].items()
    }
    baselines["no_trade"] = {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0}

    if not all_ops:
        return {
            "status": "unavailable",
            **unavailable_validation_summary("NO_HORIZON_LABELS_FROM_COMPLETED_ORDERS"),
            "data_coverage_source": "COMPLETED_SALES_ONLY",
            "reason_codes": ["NO_HORIZON_LABELS_FROM_COMPLETED_ORDERS"],
            "source": "the_show_completed_orders",
            "snapshot_kind": "historical_completed_sale",
            "source_limitations": SOURCE_LIMITATIONS,
            "model_version": MODEL_VERSION,
            "leakage_guard": _leakage_guard(lookback_orders),
            "required_orders": min_orders,
            "lookback_orders": lookback_orders,
            "horizons_days": horizons,
            "snapshots": len(snapshots),
            "cards": len(by_card),
            "evaluated_opportunities": 0,
            "trades_taken": 0,
            "trades_skipped": 0,
            "baselines": baselines,
            "horizons": horizon_metrics,
            "sample_predictions": [],
        }

    metrics = _metrics(all_ops)
    validation = validation_summary(
        metrics,
        baselines,
        sample_size=len(snapshots),
        trades_taken=len(model_trades),
        calibration_status="unavailable",
    )
    return {
        "status": "available",
        **validation,
        "data_coverage_source": "COMPLETED_SALES_ONLY",
        "reason_codes": ["COMPLETED_ORDER_DIRECTIONAL_BACKTEST_ONLY"],
        "source": "the_show_completed_orders",
        "snapshot_kind": "historical_completed_sale",
        "source_limitations": SOURCE_LIMITATIONS,
        "model_version": MODEL_VERSION,
        "leakage_guard": _leakage_guard(lookback_orders),
        "required_orders": min_orders,
        "lookback_orders": lookback_orders,
        "horizons_days": horizons,
        "tax_rate": tax_rate,
        "snapshots": len(snapshots),
        "cards": len(by_card),
        "evaluated_opportunities": len(all_ops),
        "trades_taken": len(model_trades),
        "trades_skipped": len(all_ops) - len(model_trades),
        "metrics": metrics,
        "horizons": horizon_metrics,
        "baselines": baselines,
        "sample_predictions": all_ops[:25],
    }


def evaluate_historical_snapshot_backtest(
    listings: Iterable[dict[str, Any]],
    *,
    min_snapshots: int = 30,
    lookback_snapshots: int = 9,
    horizons_days: Iterable[int] = DEFAULT_HORIZONS,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    """Run a strategy backtest from real historical bid/ask snapshots."""

    horizons = _valid_horizons(horizons_days)
    min_snapshots = max(1, int(min_snapshots or 30))
    lookback_snapshots = max(2, int(lookback_snapshots or 9))
    tax_rate = _tax_rate(tax_rate)
    snapshots: list[dict[str, Any]] = []
    for listing in listings:
        if isinstance(listing, dict):
            snapshots.extend(historical_market_snapshots_from_listing(listing))
    snapshots = _dedupe_market_snapshots(snapshots)

    by_card: dict[str, list[dict[str, Any]]] = {}
    for row in snapshots:
        by_card.setdefault(str(row["card_uuid"]), []).append(row)
    for rows in by_card.values():
        rows.sort(key=lambda r: (_parse_dt(r["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc), r["_index"]))

    baselines = _empty_market_baselines()
    if len(snapshots) < min_snapshots:
        return {
            "status": "unavailable",
            **unavailable_validation_summary("INSUFFICIENT_REAL_HISTORICAL_BID_ASK_SNAPSHOTS"),
            "data_coverage_source": "INSUFFICIENT_REAL_HISTORY",
            "reason_codes": ["INSUFFICIENT_REAL_HISTORICAL_BID_ASK_SNAPSHOTS"],
            "source": "the_show_price_history",
            "snapshot_kind": "historical_bid_ask_snapshot",
            "source_limitations": SNAPSHOT_SOURCE_LIMITATIONS,
            "model_version": "price-history-strategy-rolling-origin-v1",
            "leakage_guard": _snapshot_leakage_guard(lookback_snapshots),
            "required_snapshots": min_snapshots,
            "lookback_snapshots": lookback_snapshots,
            "horizons_days": horizons,
            "snapshots": len(snapshots),
            "cards": len(by_card),
            "evaluated_opportunities": 0,
            "trades_taken": 0,
            "trades_skipped": len(snapshots),
            "metrics": _empty_metrics(),
            "horizons": {f"{h}d": _empty_metrics() for h in horizons},
            "baselines": baselines,
            "sample_predictions": [],
        }

    opportunities_by_horizon: dict[int, list[dict[str, Any]]] = {h: [] for h in horizons}
    baseline_ops: dict[str, dict[int, list[dict[str, Any]]]] = {
        "random_trade": {h: [] for h in horizons},
        "naive_spread_only": {h: [] for h in horizons},
        "naive_momentum": {h: [] for h in horizons},
    }
    for card_uuid, rows in sorted(by_card.items()):
        if len(rows) <= lookback_snapshots:
            continue
        for idx in range(lookback_snapshots, len(rows)):
            entry = rows[idx]
            past = rows[idx - lookback_snapshots : idx]
            entry_ts = _parse_dt(entry["timestamp"])
            if entry_ts is None:
                continue
            signal = _rolling_signal([float(row["mid_price"]) for row in past])
            final_action = _snapshot_final_action(entry, signal, tax_rate=tax_rate)
            for horizon in horizons:
                future = _future_after_horizon(rows, idx, entry_ts + timedelta(days=horizon))
                if future is None:
                    continue
                realized = _snapshot_realized(entry, future, final_action=final_action, tax_rate=tax_rate)
                op = {
                    **realized,
                    "card_uuid": card_uuid,
                    "card_name": entry.get("card_name"),
                    "timestamp": entry["timestamp"],
                    "horizon_days": horizon,
                    "model_direction": signal["direction"],
                    "final_action": final_action,
                    "expected_return_proxy": signal["expected_return_proxy"],
                    "reason_codes": [*signal["reason_codes"], *_snapshot_reason_codes(entry, tax_rate=tax_rate)],
                    "taken": final_action in {"INSTANT FLIP ONLY", "SPREAD CAPTURE ONLY", "FLIP OR SHORT HOLD", "SPECULATIVE HOLD"},
                    "source_type": entry.get("source_type"),
                }
                opportunities_by_horizon[horizon].append(op)
                baseline_ops["random_trade"][horizon].append(
                    {**realized, "taken": _deterministic_coin(card_uuid, entry["timestamp"], horizon)}
                )
                baseline_ops["naive_spread_only"][horizon].append(
                    {**_snapshot_realized(entry, future, final_action="SPREAD_CAPTURE_ONLY", tax_rate=tax_rate), "taken": _has_spread_edge(entry, tax_rate=tax_rate)}
                )
                baseline_ops["naive_momentum"][horizon].append({**realized, "taken": signal["last_return"] > 0})

    horizon_metrics = {f"{h}d": _metrics(ops) for h, ops in opportunities_by_horizon.items()}
    all_ops = [op for ops in opportunities_by_horizon.values() for op in ops]
    trades = [op for op in all_ops if op.get("taken")]
    baselines["random_trade"] = {f"{h}d": _metrics(ops) for h, ops in baseline_ops["random_trade"].items()}
    baselines["naive_spread_only"] = {f"{h}d": _metrics(ops) for h, ops in baseline_ops["naive_spread_only"].items()}
    baselines["naive_momentum"] = {f"{h}d": _metrics(ops) for h, ops in baseline_ops["naive_momentum"].items()}
    baselines["old_gate_logic"] = baselines["naive_spread_only"]
    if not all_ops:
        return {
            "status": "unavailable",
            **unavailable_validation_summary("NO_HORIZON_LABELS_FROM_HISTORICAL_SNAPSHOTS"),
            "data_coverage_source": "HISTORICAL_BID_ASK_HISTORY",
            "reason_codes": ["NO_HORIZON_LABELS_FROM_HISTORICAL_SNAPSHOTS"],
            "source": "the_show_price_history",
            "snapshot_kind": "historical_bid_ask_snapshot",
            "source_limitations": SNAPSHOT_SOURCE_LIMITATIONS,
            "model_version": "price-history-strategy-rolling-origin-v1",
            "leakage_guard": _snapshot_leakage_guard(lookback_snapshots),
            "required_snapshots": min_snapshots,
            "lookback_snapshots": lookback_snapshots,
            "horizons_days": horizons,
            "snapshots": len(snapshots),
            "cards": len(by_card),
            "evaluated_opportunities": 0,
            "trades_taken": 0,
            "trades_skipped": 0,
            "metrics": _empty_metrics(),
            "horizons": horizon_metrics,
            "baselines": baselines,
            "sample_predictions": [],
        }
    metrics = _metrics(all_ops)
    validation = validation_summary(
        metrics,
        baselines,
        sample_size=len(snapshots),
        trades_taken=len(trades),
        calibration_status="unavailable",
    )
    return {
        "status": "available",
        **validation,
        "data_coverage_source": "HISTORICAL_BID_ASK_HISTORY",
        "reason_codes": ["REAL_HISTORICAL_BID_ASK_SNAPSHOT_BACKTEST"],
        "source": "the_show_price_history",
        "snapshot_kind": "historical_bid_ask_snapshot",
        "source_limitations": SNAPSHOT_SOURCE_LIMITATIONS,
        "model_version": "price-history-strategy-rolling-origin-v1",
        "leakage_guard": _snapshot_leakage_guard(lookback_snapshots),
        "required_snapshots": min_snapshots,
        "lookback_snapshots": lookback_snapshots,
        "horizons_days": horizons,
        "tax_rate": tax_rate,
        "snapshots": len(snapshots),
        "cards": len(by_card),
        "evaluated_opportunities": len(all_ops),
        "trades_taken": len(trades),
        "trades_skipped": len(all_ops) - len(trades),
        "metrics": metrics,
        "horizons": horizon_metrics,
        "baselines": baselines,
        "sample_predictions": all_ops[:25],
    }

def fetch_completed_order_backtest(
    uuids: Iterable[str],
    *,
    year: int = 26,
    min_orders: int = 30,
    lookback_orders: int = 20,
    horizons_days: Iterable[int] = DEFAULT_HORIZONS,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    """Fetch live The Show listings and run the completed-order backtest."""

    listings = [get_listing(str(uuid), year=year) for uuid in uuids]
    result = evaluate_completed_order_backtest(
        listings,
        min_orders=min_orders,
        lookback_orders=lookback_orders,
        horizons_days=horizons_days,
        tax_rate=tax_rate,
    )
    result["fetched_uuids"] = [str(uuid).lower() for uuid in uuids]
    result["year"] = int(year)
    return result


def fetch_historical_snapshot_backtest(
    uuids: Iterable[str],
    *,
    year: int = 26,
    min_snapshots: int = 30,
    lookback_snapshots: int = 9,
    horizons_days: Iterable[int] = DEFAULT_HORIZONS,
    tax_rate: float = 0.10,
) -> dict[str, Any]:
    listings = [get_listing(str(uuid), year=year) for uuid in uuids]
    result = evaluate_historical_snapshot_backtest(
        listings,
        min_snapshots=min_snapshots,
        lookback_snapshots=lookback_snapshots,
        horizons_days=horizons_days,
        tax_rate=tax_rate,
    )
    result["fetched_uuids"] = [str(uuid).lower() for uuid in uuids]
    result["year"] = int(year)
    return result


def _rolling_signal(prices: list[float]) -> dict[str, Any]:
    returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] > 0 and math.isfinite(prices[i])
    ]
    if not returns:
        return {
            "direction": "INSUFFICIENT DATA",
            "final_action": "WATCHLIST / NO MODEL TRADE",
            "expected_return_proxy": None,
            "last_return": 0.0,
            "reason_codes": ["NO_PAST_RETURNS"],
        }
    avg = mean(returns)
    med = median(returns)
    last = returns[-1]
    vol = stdev(returns) if len(returns) > 1 else 0.0
    threshold = max(0.0025, min(0.02, vol * 0.20))
    if med > threshold and avg > 0:
        return {
            "direction": "BULLISH",
            "final_action": "SPECULATIVE HOLD",
            "expected_return_proxy": avg,
            "last_return": last,
            "reason_codes": ["PAST_COMPLETED_SALE_DRIFT_POSITIVE"],
        }
    if med < -threshold and avg < 0:
        return {
            "direction": "BEARISH",
            "final_action": "AVOID",
            "expected_return_proxy": avg,
            "last_return": last,
            "reason_codes": ["PAST_COMPLETED_SALE_DRIFT_NEGATIVE"],
        }
    return {
        "direction": "NEUTRAL",
        "final_action": "WATCHLIST / NO MODEL TRADE",
        "expected_return_proxy": avg,
        "last_return": last,
        "reason_codes": ["NO_ROLLING_COMPLETED_SALE_EDGE"],
    }


def _realized_hold(entry: dict[str, Any], future: dict[str, Any], *, tax_rate: float) -> dict[str, Any]:
    entry_price = float(entry["sale_price"])
    exit_price = float(future["sale_price"])
    exit_after_tax = exit_price * (1 - tax_rate)
    net_stubs = exit_after_tax - entry_price
    entry_ts = _parse_dt(entry["timestamp"])
    exit_ts = _parse_dt(future["timestamp"])
    holding_days = None
    if entry_ts is not None and exit_ts is not None:
        holding_days = (exit_ts - entry_ts).total_seconds() / 86400.0
    return {
        "strategy_family": "directional_completed_sale_hold",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_after_tax": exit_after_tax,
        "net_stubs": net_stubs,
        "roi": net_stubs / entry_price if entry_price else 0.0,
        "hit": net_stubs > 0,
        "failed_exit": net_stubs <= 0,
        "fill_probability_proxy": None,
        "execution_assumption": "completed-sale hold buys at observed sale price and exits at the first future completed sale after tax",
        "exit_timestamp": future["timestamp"],
        "actual_holding_days": holding_days,
    }


def _future_after_horizon(
    rows: list[dict[str, Any]],
    entry_idx: int,
    target_ts: datetime,
) -> dict[str, Any] | None:
    for row in rows[entry_idx + 1 :]:
        ts = _parse_dt(row["timestamp"])
        if ts is not None and ts >= target_ts:
            return row
    return None


def _snapshot_final_action(entry: dict[str, Any], signal: dict[str, Any], *, tax_rate: float) -> str:
    spread = _has_spread_edge(entry, tax_rate=tax_rate)
    direction = signal["direction"]
    if spread and direction == "BEARISH":
        return "INSTANT FLIP ONLY"
    if spread and direction == "BULLISH":
        return "FLIP OR SHORT HOLD"
    if spread and direction == "NEUTRAL":
        return "SPREAD CAPTURE ONLY"
    if not spread and direction == "BULLISH":
        return "SPECULATIVE HOLD"
    if not spread and direction == "BEARISH":
        return "AVOID"
    return "WATCHLIST / NO MODEL TRADE"


def _snapshot_realized(
    entry: dict[str, Any],
    future: dict[str, Any],
    *,
    final_action: str,
    tax_rate: float,
) -> dict[str, Any]:
    entry_bid = float(entry["raw_bid"])
    current_exit = float(entry["raw_ask"]) * (1 - tax_rate)
    future_exit = float(future["raw_ask"]) * (1 - tax_rate)
    if final_action in {"INSTANT FLIP ONLY", "SPREAD_CAPTURE_ONLY", "SPREAD CAPTURE ONLY"}:
        exit_value = current_exit
        exit_timestamp = entry["timestamp"]
        family = "spread_capture"
        assumption = "limit buy at historical bid, relist at historical ask, no queue-depth proof"
    elif final_action == "FLIP OR SHORT HOLD":
        exit_value = future_exit
        exit_timestamp = future["timestamp"]
        family = "flip_or_short_hold"
        assumption = "limit buy at historical bid, hold to future ask, no queue-depth proof"
    else:
        exit_value = future_exit
        exit_timestamp = future["timestamp"]
        family = "directional_hold"
        assumption = "directional snapshot hold uses historical bid entry and future ask exit after tax"
    net_stubs = exit_value - entry_bid
    entry_ts = _parse_dt(entry["timestamp"])
    exit_ts = _parse_dt(exit_timestamp)
    holding_days = None
    if entry_ts is not None and exit_ts is not None:
        holding_days = max(0.0, (exit_ts - entry_ts).total_seconds() / 86400.0)
    return {
        "strategy_family": family,
        "entry_price": entry_bid,
        "exit_price": exit_value / (1 - tax_rate) if tax_rate < 1 else exit_value,
        "exit_after_tax": exit_value,
        "net_stubs": net_stubs,
        "roi": net_stubs / entry_bid if entry_bid else 0.0,
        "hit": net_stubs > 0,
        "failed_exit": net_stubs <= 0,
        "fill_probability_proxy": None,
        "execution_assumption": assumption,
        "exit_timestamp": exit_timestamp,
        "actual_holding_days": holding_days,
    }


def _snapshot_reason_codes(entry: dict[str, Any], *, tax_rate: float) -> list[str]:
    return ["REAL_BID_ASK_SPREAD_EDGE"] if _has_spread_edge(entry, tax_rate=tax_rate) else ["NO_REAL_BID_ASK_SPREAD_EDGE"]


def _has_spread_edge(entry: dict[str, Any], *, tax_rate: float) -> bool:
    bid = _num(entry.get("raw_bid"))
    ask = _num(entry.get("raw_ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return False
    net = ask * (1 - tax_rate) - bid
    roi = net / bid if bid else 0.0
    return net > 0 and roi >= 0.01


def _metrics(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    trades = [op for op in opportunities if op.get("taken")]
    rois = [float(op["roi"]) for op in trades]
    stubs = [float(op["net_stubs"]) for op in trades]
    equity = _equity_curve(stubs)
    holding_days = [float(op["actual_holding_days"]) for op in trades if op.get("actual_holding_days") is not None]
    return {
        "evaluated_opportunities": len(opportunities),
        "trades_taken": len(trades),
        "trades_skipped": len(opportunities) - len(trades),
        "average_roi": mean(rois) if rois else None,
        "median_roi": median(rois) if rois else None,
        "total_stubs": sum(stubs),
        "hit_rate": sum(1 for x in stubs if x > 0) / len(stubs) if stubs else None,
        "profit_factor": _profit_factor(stubs),
        "max_drawdown": _max_drawdown(equity),
        "sharpe_like": _ratio(rois),
        "sortino_like": _ratio([x for x in rois if x < 0]),
        "average_holding_time_days": mean(holding_days) if holding_days else None,
        "failed_exit_rate": sum(1 for op in trades if op.get("failed_exit")) / len(trades) if trades else None,
        "turnover_velocity": len(trades) / max(1, len(opportunities)),
        "stub_velocity": sum(stubs) / max(1, len(opportunities)),
        "opportunity_cost_estimate": 0.0,
    }


def _empty_metrics() -> dict[str, Any]:
    return _metrics([])


def _empty_baselines() -> dict[str, Any]:
    return {
        "no_trade": {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0},
        "random_trade": {"status": "unavailable until horizon labels exist"},
        "naive_spread_only": {
            "status": "unavailable",
            "reason": "completed_orders do not include historical bid/ask depth",
        },
        "naive_momentum": {"status": "unavailable until horizon labels exist"},
        "naive_no_change_forecast": {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0},
        "old_gate_logic": {
            "status": "unavailable",
            "reason": "old gate logic requires contemporaneous forecast/gate snapshots",
        },
    }


def _empty_market_baselines() -> dict[str, Any]:
    return {
        "no_trade": {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0},
        "random_trade": {"status": "unavailable until horizon labels exist"},
        "naive_spread_only": {"status": "unavailable until horizon labels exist"},
        "naive_momentum": {"status": "unavailable until horizon labels exist"},
        "naive_no_change_forecast": {"trades_taken": 0, "total_stubs": 0.0, "roi": 0.0},
        "old_gate_logic": {"status": "unavailable until horizon labels exist"},
    }


def _leakage_guard(lookback_orders: int) -> dict[str, Any]:
    return {
        "method": "rolling_origin_completed_orders",
        "feature_window": f"previous {lookback_orders} completed-sale observations only",
        "label_window": "first future completed sale at or after requested horizon",
        "future_features_allowed": False,
        "deterministic_sort": ["card_uuid", "timestamp", "_index"],
    }


def _snapshot_leakage_guard(lookback_snapshots: int) -> dict[str, Any]:
    return {
        "method": "rolling_origin_price_history_snapshots",
        "feature_window": f"previous {lookback_snapshots} historical bid/ask snapshots only",
        "label_window": "future historical bid/ask snapshot at or after requested horizon",
        "future_features_allowed": False,
        "deterministic_sort": ["card_uuid", "timestamp", "_index"],
    }


def _dedupe_sale_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, float]] = set()
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: (str(r.get("card_uuid")), str(r.get("timestamp")), int(r.get("_index") or 0))):
        price = _num(row.get("sale_price"))
        key = (str(row.get("card_uuid") or ""), str(row.get("timestamp") or ""), float(price or 0.0))
        if not key[0] or not key[1] or price is None or key in seen:
            continue
        seen.add(key)
        row = dict(row)
        row["_index"] = len(out)
        out.append(row)
    return out


def _dedupe_market_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, float, float]] = set()
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: (str(r.get("card_uuid")), str(r.get("timestamp")), int(r.get("_index") or 0))):
        ask = _num(row.get("raw_ask"))
        bid = _num(row.get("raw_bid"))
        key = (
            str(row.get("card_uuid") or ""),
            str(row.get("timestamp") or ""),
            float(ask or 0.0),
            float(bid or 0.0),
        )
        if not key[0] or not key[1] or ask is None or bid is None or key in seen:
            continue
        seen.add(key)
        row = dict(row)
        row["_index"] = len(out)
        out.append(row)
    return out


def _valid_horizons(values: Iterable[int]) -> list[int]:
    out: list[int] = []
    for raw in values:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value <= 30 and value not in out:
            out.append(value)
    return out or list(DEFAULT_HORIZONS)


def _deterministic_coin(card_uuid: str, timestamp: str, horizon: int) -> bool:
    digest = hashlib.sha256(f"{card_uuid}|{timestamp}|{horizon}|{MODEL_VERSION}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2 == 0


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _tax_rate(value: Any) -> float:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return 0.10
    if not math.isfinite(rate):
        return 0.10
    return max(0.0, min(0.50, rate))


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _equity_curve(values: list[float]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for value in values:
        total += value
        out.append(total)
    return out


def _max_drawdown(equity: list[float]) -> float | None:
    if not equity:
        return None
    peak = equity[0]
    drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value - peak)
    return drawdown


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return None
    return gains / losses


def _ratio(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    sd = stdev(values)
    return mean(values) / sd if sd > 0 else None

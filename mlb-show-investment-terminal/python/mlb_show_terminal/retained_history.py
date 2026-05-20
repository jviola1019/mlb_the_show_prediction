"""Retained market-history discovery and ledger import helpers.

These utilities gather only real upstream records:
- The Show listing ``price_history`` rows for retained bid/ask snapshots.
- The Show listing ``completed_orders`` rows for retained sale prints.
- User/exported ledger rows supplied as CSV/JSON.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable

from .artifacts import write_json
from .completed_order_backtesting import (
    completed_order_snapshots_from_listing,
    evaluate_completed_order_backtest,
    evaluate_historical_snapshot_backtest,
    historical_market_snapshots_from_listing,
)
from .ledger import persist_ledger_row, realized_trade_metrics
from .theshow import discover_top_listings, get_listing


DEFAULT_RARITIES = ("Diamond", "Gold", "Silver")


def collect_retained_market_history(
    *,
    rarities: Iterable[str] = DEFAULT_RARITIES,
    per_rarity: int = 15,
    year: int = 26,
    rate_delay: float = 0.15,
    include_rows: bool = False,
) -> dict[str, Any]:
    """Fetch a bounded card universe and summarize retained real history."""

    listings: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[dict[str, Any]] = []
    limit = max(1, min(int(per_rarity or 15), 100))
    for rarity in [str(x) for x in rarities if str(x).strip()]:
        try:
            top = discover_top_listings(rarity=rarity, top_n=limit, year=year, pages=30)
        except Exception as exc:  # pragma: no cover - network dependent
            errors.append({"rarity": rarity, "error": str(exc)})
            continue
        for uuid in top.get("uuids") or []:
            uuid = str(uuid).lower()
            if not uuid or uuid in seen:
                continue
            seen.add(uuid)
            try:
                listings.append(get_listing(uuid, year=year))
            except Exception as exc:  # pragma: no cover - network dependent
                errors.append({"rarity": rarity, "uuid": uuid, "error": str(exc)})
            if rate_delay > 0:
                time.sleep(min(float(rate_delay), 5.0))
    return summarize_retained_market_history(
        listings,
        rarities=list(rarities),
        per_rarity=limit,
        year=year,
        errors=errors,
        include_rows=include_rows,
    )


def summarize_retained_market_history(
    listings: Iterable[dict[str, Any]],
    *,
    rarities: list[str] | None = None,
    per_rarity: int | None = None,
    year: int = 26,
    errors: list[dict[str, Any]] | None = None,
    include_rows: bool = False,
) -> dict[str, Any]:
    listing_list = [row for row in listings if isinstance(row, dict)]
    bid_ask: list[dict[str, Any]] = []
    sales: list[dict[str, Any]] = []
    for listing in listing_list:
        bid_ask.extend(historical_market_snapshots_from_listing(listing))
        sales.extend(completed_order_snapshots_from_listing(listing))

    hist_backtest = evaluate_historical_snapshot_backtest(
        listing_list,
        min_snapshots=30,
        lookback_snapshots=5,
        horizons_days=[1, 3, 7],
        tax_rate=0.10,
    )
    sale_backtest = evaluate_completed_order_backtest(
        listing_list,
        min_orders=30,
        lookback_orders=20,
        horizons_days=[1, 3, 7],
        tax_rate=0.10,
    )
    out: dict[str, Any] = {
        "generated_at": _utc_now(),
        "source": "The Show listing API",
        "year": int(year),
        "rarities_requested": rarities or [],
        "per_rarity_requested": per_rarity,
        "cards_fetched": len(listing_list),
        "historical_bid_ask_snapshots_found": len(bid_ask),
        "completed_sale_snapshots_found": len(sales),
        "price_history_dates": sorted({str(row["timestamp"])[:10] for row in bid_ask if row.get("timestamp")}),
        "completed_sale_date_range": [
            min((str(row["timestamp"]) for row in sales if row.get("timestamp")), default=None),
            max((str(row["timestamp"]) for row in sales if row.get("timestamp")), default=None),
        ],
        "historical_snapshot_backtest": _backtest_summary(hist_backtest),
        "completed_order_backtest": _backtest_summary(sale_backtest),
        "sample_cards": [_listing_summary(listing) for listing in listing_list[:25]],
        "errors": errors or [],
        "source_limitations": [
            "price_history retention depth varies by card",
            "completed_orders are sale prints, not bid/ask depth",
            "user-specific realized ledger outcomes require user-supplied exports or manual trade logs",
        ],
    }
    if include_rows:
        out["historical_bid_ask_snapshots"] = bid_ask
        out["completed_sale_snapshots"] = sales
    return out


def summarize_external_ledger(
    rows: Iterable[dict[str, Any]],
    *,
    source_name: str = "user_supplied",
    persist: bool = False,
) -> dict[str, Any]:
    """Normalize user-supplied realized outcomes without inventing fields."""

    row_list = [row for row in rows if isinstance(row, dict)]
    normalized: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    write_results: list[dict[str, Any]] = []
    for idx, raw in enumerate(row_list):
        row = _normalize_ledger_row(raw, source_name=source_name)
        missing = [field for field in ("card_uuid", "buy_price", "timestamp", "strategy_type") if row.get(field) in (None, "")]
        if missing:
            invalid.append({"row_index": idx, "missing": missing, "raw": raw})
            continue
        normalized.append(row)
        if persist:
            write_results.append(persist_ledger_row(row))
    return {
        "status": "ok",
        "source_name": source_name,
        "rows_received": len(row_list),
        "valid_rows": len(normalized),
        "invalid_rows": len(invalid),
        "metrics": realized_trade_metrics(normalized),
        "normalized_rows": normalized,
        "invalid": invalid,
        "persistence": write_results,
    }


def write_retained_history_artifact(path: str | Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _listing_summary(listing: dict[str, Any]) -> dict[str, Any]:
    item = listing.get("item") if isinstance(listing.get("item"), dict) else {}
    return {
        "uuid": item.get("uuid"),
        "name": item.get("name") or listing.get("listing_name"),
        "rarity": item.get("rarity"),
        "source_url": listing.get("source_url") or listing.get("_source_url"),
        "price_history_rows": len(historical_market_snapshots_from_listing(listing)),
        "completed_order_rows": len(completed_order_snapshots_from_listing(listing)),
    }


def _backtest_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "validation_tier": payload.get("validation_tier"),
        "data_coverage_tier": payload.get("data_coverage_tier"),
        "performance_validation_tier": payload.get("performance_validation_tier"),
        "data_coverage_source": payload.get("data_coverage_source"),
        "validation_verdict": payload.get("validation_verdict"),
        "baseline_comparison": payload.get("baseline_comparison"),
        "snapshots": payload.get("snapshots"),
        "cards": payload.get("cards"),
        "evaluated_opportunities": payload.get("evaluated_opportunities"),
        "trades_taken": payload.get("trades_taken"),
        "reason_codes": payload.get("reason_codes"),
        "horizons": payload.get("horizons"),
    }


def _normalize_ledger_row(raw: dict[str, Any], *, source_name: str) -> dict[str, Any]:
    raw = _clean_row_keys(raw)
    return {
        "card_uuid": _first(raw, "card_uuid", "uuid", "item_uuid"),
        "card_name": _first(raw, "card_name", "name", "player"),
        "strategy_type": _first(raw, "strategy_type", "strategy", default="external_manual"),
        "buy_price": _first(raw, "buy_price", "buy", "entry_price"),
        "sell_price": _first(raw, "sell_price", "sell", "exit_price"),
        "exit_price": _first(raw, "exit_price", "sell_price", "sell"),
        "tax": _first(raw, "tax", "tax_rate", default=0.10),
        "slippage": _first(raw, "slippage", default=0),
        "fill_status": _first(raw, "fill_status", "status", default="closed"),
        "time_to_fill_minutes": _first(raw, "time_to_fill_minutes", "time_to_fill"),
        "holding_time_hours": _first(raw, "holding_time_hours", "holding_hours"),
        "expected_net_stubs": _first(raw, "expected_net_stubs", "expected_profit"),
        "timestamp": _first(raw, "timestamp", "date", "created_at"),
        "model_prediction": {"source_name": source_name, "raw": raw},
    }


def _first(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return default


def _clean_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        cleaned[str(key).lstrip("\ufeff").strip()] = value
    return cleaned


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

"""Forward collector for real market snapshots and prediction audit rows."""

from __future__ import annotations

import time
from typing import Any

from .persistence import write_table
from .provenance import stable_hash


def collect_market_snapshot(listing: dict[str, Any], strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    item = listing.get("item") or {}
    if not item.get("uuid"):
        return {"status": "skipped", "reason": "missing card uuid"}
    payload = {
        "card_uuid": item.get("uuid"),
        "card_name": item.get("name") or listing.get("listing_name"),
        "rarity": item.get("rarity"),
        "team": item.get("team"),
        "position": item.get("display_position"),
        "raw_ask": listing.get("best_sell_price"),
        "raw_bid": listing.get("best_buy_price"),
        "source_url": listing.get("source_url"),
        "source_timestamp": listing.get("fetched_at"),
        "pulled_at": listing.get("fetched_at") or _utc_now(),
        "raw_hash": stable_hash(listing),
        "strategy": strategy or {},
    }
    return write_table("market_snapshots", payload)


def collect_model_prediction(record: dict[str, Any]) -> dict[str, Any]:
    strategy = record.get("strategy") if isinstance(record.get("strategy"), dict) else {}
    if not record.get("uuid") or not strategy:
        return {"status": "skipped", "reason": "missing uuid or strategy"}
    payload = {
        "card_uuid": record.get("uuid"),
        "prediction_timestamp": record.get("fetched_at") or _utc_now(),
        "final_action": ((strategy.get("composite") or {}).get("final_action")),
        "strategy": strategy,
        "provenance": record.get("provenance") or {},
        "raw_hash": stable_hash({"uuid": record.get("uuid"), "strategy": strategy}),
    }
    return write_table("model_predictions", payload)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

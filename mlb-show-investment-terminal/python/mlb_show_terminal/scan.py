"""Market scan orchestration and partitioning."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from .artifacts import score_row
from .forecast import forecast_diagnostics
from .mlb_stats import MLBStatsError, recent_vs_season
from .theshow import TheShowError, discover_top_listings, get_listing
from .uuid_tools import parse_uuid_tokens


ProgressCallback = Any


def _csv(values: Any) -> str:
    if isinstance(values, str):
        return values
    if isinstance(values, list):
        return ",".join(str(v) for v in values if v)
    return ""


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def listing_to_row(listing: dict[str, Any], stats: dict[str, Any] | None = None) -> dict[str, Any]:
    item = listing.get("item") or {}
    orders = listing.get("completed_orders") or []
    recent = 0
    # The Show completed_orders payload is already recent-biased; use count as a
    # conservative liquidity proxy for scanner ranking.
    if isinstance(orders, list):
        recent = min(len(orders), 200)
    row = {
        "uuid": item.get("uuid"),
        "name": item.get("name") or listing.get("listing_name"),
        "rarity": item.get("rarity"),
        "team": item.get("team"),
        "team_short_name": item.get("team_short_name"),
        "display_position": item.get("display_position"),
        "series": item.get("series"),
        "img": item.get("img"),
        "baked_img": item.get("baked_img"),
        "current_ovr": item.get("ovr") or item.get("rank"),
        "new_rank": item.get("new_rank"),
        "raw_ask": listing.get("best_sell_price"),
        "raw_bid": listing.get("best_buy_price"),
        "liquidity_score": min(1.0, recent / 150) if recent else None,
        "liquidity_n": len(orders) if isinstance(orders, list) else 0,
        "liquidity_recent": recent,
    }
    if stats:
        row.update({
            "role": stats.get("role", "hitter"),
            "recent": stats.get("recent") or {},
            "season": stats.get("season") or {},
        })
    return row


def _stats_for_listing(listing: dict[str, Any]) -> dict[str, Any] | None:
    item = listing.get("item") or {}
    name = item.get("name") or listing.get("listing_name")
    if not name:
        return None
    try:
        return recent_vs_season(str(name))
    except (MLBStatsError, Exception):
        return None


def _status_from_record(record: dict[str, Any]) -> str:
    if record.get("status") == "dropped":
        return "INVALID"
    flip = record.get("flip") or {}
    upgrade = record.get("upgrade") or {}
    if flip.get("action") == "NO TRADE" and upgrade.get("action") == "AVOID":
        return "INVALID"
    return "VALID"


def _verdict_from_record(record: dict[str, Any]) -> str:
    if record.get("status") == "dropped":
        return "NOT INVESTABLE"
    flip = record.get("flip") or {}
    upgrade = record.get("upgrade") or {}
    if flip.get("action") == "BUY" or upgrade.get("action") == "BUY SPECULATIVE":
        return "INVESTABLE"
    if flip.get("action") == "SELL" or upgrade.get("action") == "SELL":
        return "RISK EXIT"
    return "OBSERVATIONAL ONLY"


def enrich_scan_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Expose Shiny-era scan columns while preserving nested API payloads."""

    card = record.get("card") or {}
    flip = record.get("flip") or {}
    upgrade = record.get("upgrade") or {}
    forecast = record.get("forecast") or {}
    gates = forecast.get("gates") if isinstance(forecast.get("gates"), dict) else {}
    validation = record.get("validation") if isinstance(record.get("validation"), dict) else {}
    if record.get("status") == "dropped":
        reason = record.get("reason") or "fetch_error"
        record.update({
            "name": record.get("name") or "-",
            "scan_status": "INVALID",
            "verdict_status": "NOT INVESTABLE",
            "tier": "UNRATED",
            "flip_reason_codes": str(reason),
            "upgrade_reason_codes": "",
            "gates_failed_csv": str(reason),
            "forecast_direction": "FORECAST UNAVAILABLE",
            "forecast_ev_7d": None,
        })
        return record

    record.update({
        "raw_bid": _first(flip.get("buy_price"), card.get("raw_bid"), card.get("bid")),
        "raw_ask": _first(flip.get("sell_price"), card.get("raw_ask"), card.get("ask")),
        "after_tax_sale": flip.get("after_tax_sale"),
        "flip_profit": flip.get("profit"),
        "flip_roi": flip.get("roi"),
        "spread_pct": flip.get("spread_pct"),
        "liquidity_score": _first(flip.get("liquidity_score"), card.get("liquidity_score")),
        "liquidity_n": _first(flip.get("liquidity_n"), card.get("liquidity_n")),
        "liquidity_recent": _first(flip.get("liquidity_recent"), card.get("liquidity_recent")),
        "flip_executable": flip.get("executable"),
        "flip_action": flip.get("action"),
        "flip_reason_codes": _csv(flip.get("reason_codes") or flip.get("reason_codes_csv")),
        "flip_failed_gates": _csv(flip.get("failed_gates") or flip.get("failed_gates_csv")),
        "ovr": _first(upgrade.get("current_ovr"), card.get("current_ovr"), card.get("ovr")),
        "new_rank": upgrade.get("new_rank"),
        "next_threshold": upgrade.get("next_threshold"),
        "distance_to_threshold": upgrade.get("distance_to_threshold"),
        "distance_to_85": upgrade.get("distance_to_85"),
        "distance_to_90": upgrade.get("distance_to_90"),
        "p_upgrade": upgrade.get("p_upgrade"),
        "p_downgrade": upgrade.get("p_downgrade"),
        "p_cross_next_threshold": upgrade.get("p_cross_next_threshold"),
        "p_cross_85": upgrade.get("p_cross_85"),
        "p_cross_90": upgrade.get("p_cross_90"),
        "upgrade_confidence": upgrade.get("confidence"),
        "upgrade_score": upgrade.get("upgrade_score"),
        "upgrade_action": upgrade.get("action"),
        "upgrade_reason_codes": _csv(upgrade.get("reason_codes") or upgrade.get("reason_codes_csv")),
        "forecast_direction": forecast.get("direction") or forecast.get("status") or "FORECAST UNAVAILABLE",
        "forecast_ev_7d": forecast.get("expected_ret"),
        "forecast_p_up_7d": forecast.get("p_profit"),
        "forecast_score": None,
        "forecast_action": "HOLD",
        "scan_status": _status_from_record(record),
        "verdict_status": _verdict_from_record(record),
        "tier": forecast.get("tier") or "UNRATED",
        "gates_failed_csv": gates.get("failed_csv") or "",
        "validation_mismatch": validation.get("mismatch"),
    })
    return record


def analyze_listing(
    listing: dict[str, Any],
    *,
    stats: dict[str, Any] | None = None,
    enrich_mlb_stats: bool = False,
) -> dict[str, Any]:
    if stats is None and enrich_mlb_stats:
        stats = _stats_for_listing(listing)
    row = listing_to_row(listing, stats=stats)
    scored = score_row(row)
    scored["card"] = row
    scored["uuid"] = row.get("uuid")
    scored["name"] = row.get("name")
    scored["fetched_at"] = listing.get("fetched_at")
    scored["source_url"] = listing.get("source_url")
    scored["forecast"] = forecast_diagnostics(listing)
    scored["decision_channels"] = {
        "flip": scored["flip"]["action"],
        "upgrade": scored["upgrade"]["action"],
        "forecast": scored["forecast"].get("direction", "FORECAST UNAVAILABLE"),
    }
    return enrich_scan_fields(scored)


def partition_scan(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {"flip_buys": [], "upgrade_buys": [], "holds": [], "sells": [], "dropped": []}
    for rec in records:
        enrich_scan_fields(rec)
        if rec.get("status") == "dropped":
            buckets["dropped"].append(rec)
            continue
        flip = rec.get("flip") or {}
        upgrade = rec.get("upgrade") or {}
        if flip.get("action") == "BUY":
            buckets["flip_buys"].append(rec)
        elif upgrade.get("action") == "BUY SPECULATIVE":
            buckets["upgrade_buys"].append(rec)
        elif flip.get("action") == "SELL" or upgrade.get("action") == "SELL":
            buckets["sells"].append(rec)
        else:
            buckets["holds"].append(rec)

    buckets["flip_buys"].sort(key=lambda r: ((r.get("flip") or {}).get("roi") or -999), reverse=True)
    buckets["upgrade_buys"].sort(key=lambda r: ((r.get("upgrade") or {}).get("upgrade_score") or -999), reverse=True)
    buckets["sells"].sort(key=lambda r: ((r.get("flip") or {}).get("roi") or 999))
    return buckets


def _dropped_record(uuid: str, reason: str, *, idx: int, total: int, name: str | None = None) -> dict[str, Any]:
    return enrich_scan_fields({
        "status": "dropped",
        "uuid": uuid,
        "name": name,
        "reason": reason,
        "scan_index": idx,
        "scan_total": total,
    })


def _scan_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    tiers = Counter(str(row.get("tier") or "UNRATED") for row in records if row.get("status") != "dropped")
    spreads = [float(row["spread_pct"]) for row in records if isinstance(row.get("spread_pct"), (int, float))]
    liq = [float(row["liquidity_recent"]) for row in records if isinstance(row.get("liquidity_recent"), (int, float))]
    return {
        "tier_distribution": dict(tiers),
        "market_health": {
            "median_spread": sorted(spreads)[len(spreads) // 2] if spreads else None,
            "median_liquidity_recent": sorted(liq)[len(liq) // 2] if liq else None,
            "cards_with_forecast_warnings": sum(1 for row in records if row.get("gates_failed_csv")),
            "cards_with_positive_flip_roi": sum(1 for row in records if isinstance(row.get("flip_roi"), (int, float)) and row["flip_roi"] > 0),
        },
        "dropped_summary": dict(Counter(str(row.get("reason") or row.get("flip_reason_codes") or "unknown") for row in records if row.get("status") == "dropped")),
    }


def scan_payload(payload: dict[str, Any], progress: ProgressCallback | None = None) -> dict[str, Any]:
    started = time.time()
    mode = str(payload.get("mode") or "paste_uuids")
    year = int(payload.get("year") or 26)
    rate_delay = float(payload.get("rate_delay") if payload.get("rate_delay") is not None else 1.5)
    enrich_mlb_stats = bool(payload.get("enrich_mlb_stats", True))
    discovered: dict[str, Any] | None = None
    uuid_source: Any = payload.get("uuids") or payload.get("uuid_text") or ""
    if mode == "top_live":
        if progress:
            progress({"status": "running", "current_name": "discovering top live universe"})
        discovered = discover_top_listings(
            rarity=str(payload.get("rarity") or "Gold"),
            top_n=int(payload.get("top_n") or 25),
            year=year,
        )
        uuid_source = discovered.get("uuids", [])
    elif mode == "session_history":
        uuid_source = payload.get("session_uuids") or payload.get("uuids") or payload.get("uuid_text") or ""

    parsed = parse_uuid_tokens(uuid_source)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    stats_by_uuid = payload.get("stats_by_uuid") if isinstance(payload.get("stats_by_uuid"), dict) else {}
    records: list[dict[str, Any]] = []

    for row in rows:
        if isinstance(row, dict):
            scored = score_row(row)
            scored["card"] = row
            scored["forecast"] = {
                "status": "unavailable",
                "diagnostic_only": True,
                "reason": "listing payload required for price-history diagnostics",
                "gates": {
                    "status": "diagnostic_warning",
                    "failed": ["listing_required"],
                    "failed_csv": "listing_required",
                    "note": "Forecast gates do not block executable flip or upgrade signals.",
                },
                "tier": "UNRATED",
            }
            records.append(enrich_scan_fields(scored))

    total = len(parsed.uuids)
    dropped_count = 0
    for idx, uuid in enumerate(parsed.uuids, start=1):
        if progress:
            progress({
                "status": "running",
                "total": total + len(rows),
                "completed": len(records),
                "current_uuid": uuid,
                "current_name": "fetching listing",
                "dropped_count": dropped_count,
                "invalid_count": len(parsed.invalid_tokens),
            })
        try:
            listing = get_listing(uuid, year=year)
            item = listing.get("item") or {}
            if progress:
                progress({
                    "status": "running",
                    "total": total + len(rows),
                    "completed": len(records),
                    "current_uuid": uuid,
                    "current_name": item.get("name") or listing.get("listing_name") or uuid,
                    "dropped_count": dropped_count,
                    "invalid_count": len(parsed.invalid_tokens),
                })
            rec = analyze_listing(
                listing,
                stats=stats_by_uuid.get(uuid),
                enrich_mlb_stats=enrich_mlb_stats and uuid not in stats_by_uuid,
            )
            rec["scan_index"] = idx
            rec["scan_total"] = total
            records.append(enrich_scan_fields(rec))
        except (TheShowError, Exception) as exc:  # pragma: no cover - network dependent
            dropped_count += 1
            records.append(_dropped_record(uuid, str(exc), idx=idx, total=total))
        if progress:
            progress({
                "status": "running",
                "total": total + len(rows),
                "completed": len(records),
                "current_uuid": uuid,
                "current_name": records[-1].get("name") or uuid,
                "dropped_count": dropped_count,
                "invalid_count": len(parsed.invalid_tokens),
            })
        if idx < total and rate_delay > 0:
            time.sleep(rate_delay)

    parts = partition_scan(records)
    elapsed = round(time.time() - started, 3)
    summary = _scan_summary(records)
    return {
        "uuid_parse": parsed.to_dict(),
        "mode": mode,
        "rarity": payload.get("rarity"),
        "top_n": payload.get("top_n"),
        "discovered": discovered,
        "progress": {
            "total": total + len(rows),
            "completed": len(records),
            "current_uuid": None,
            "current_name": None,
            "dropped_count": len(parts["dropped"]),
            "invalid_count": len(parsed.invalid_tokens),
            "status": "complete",
            "elapsed_seconds": elapsed,
            "rate_limit_message": "The Show API calls are server-side and may be rate limited; large scans should be batched.",
        },
        "records": records,
        "partitions": parts,
        "counts": {key: len(value) for key, value in parts.items()},
        "tier_distribution": summary["tier_distribution"],
        "market_health": summary["market_health"],
        "dropped_summary": summary["dropped_summary"],
    }

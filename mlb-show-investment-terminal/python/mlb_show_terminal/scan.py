"""Market scan orchestration and partitioning."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from .artifacts import score_row
from .collector import collect_market_snapshot, collect_model_prediction
from .forecast import forecast_diagnostics
from .mlb_stats import MLBStatsError, recent_vs_season
from .provenance import provenance_for_listing
from .strategy_matrix import build_strategy_record
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
    return "VALID"


def _verdict_from_record(record: dict[str, Any]) -> str:
    """Read the governance verdict directly from the forecast block.

    The 7-gate governance system (governance.py) is the single source of truth.
    Fall back to flip/upgrade action labels only when no forecast was produced.
    """
    if record.get("status") == "dropped":
        return "NOT INVESTABLE"
    forecast = record.get("forecast") or {}
    verdict = forecast.get("verdict") if isinstance(forecast.get("verdict"), dict) else {}
    status = verdict.get("status")
    if status in ("INVESTABLE", "OBSERVATIONAL ONLY", "NOT INVESTABLE"):
        return str(status)
    return "OBSERVATIONAL ONLY"


def _listify(values: Any) -> list[str]:
    if isinstance(values, list):
        return [str(value) for value in values if value]
    if isinstance(values, str):
        return [part.strip() for part in values.split(",") if part.strip()]
    return []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _decision_for_record(record: dict[str, Any]) -> dict[str, Any]:
    """Build the final row decision without overwriting channel details."""

    if record.get("status") == "dropped":
        reason = str(record.get("reason") or "fetch_error")
        return {
            "action": "DROPPED / INVALID",
            "responsible_channel": "invalid",
            "reason_codes": _unique(["DROPPED_INVALID", reason]),
            "reason_codes_csv": _csv(["DROPPED_INVALID", reason]),
            "blockers": [reason],
            "blockers_csv": reason,
            "formula_inputs": {},
            "confidence": 0,
            "model_status": "invalid_or_fetch_failed",
            "probability_kind": "none",
            "explanation": f"Row was dropped because {reason}.",
        }

    strategy = record.get("strategy") if isinstance(record.get("strategy"), dict) else {}
    composite = strategy.get("composite") if isinstance(strategy.get("composite"), dict) else {}
    if composite.get("final_action"):
        strat_flip = strategy.get("flip") if isinstance(strategy.get("flip"), dict) else {}
        strat_dir = strategy.get("directional") if isinstance(strategy.get("directional"), dict) else {}
        strat_inv = strategy.get("inventory") if isinstance(strategy.get("inventory"), dict) else {}
        action = str(composite.get("final_action"))
        reasons = _listify(composite.get("reason_codes"))
        blockers = _listify(composite.get("gates_failed"))
        formula_inputs = {
            "sell_price": strat_flip.get("raw_ask"),
            "buy_price": strat_flip.get("raw_bid"),
            "after_tax_sale": strat_flip.get("after_tax_resale_value"),
            "profit": strat_flip.get("expected_net_stubs"),
            "roi": strat_flip.get("expected_roi_after_tax_and_friction"),
            "p_exit": strat_flip.get("p_successful_exit"),
            "expected_exit_hours": strat_inv.get("expected_exit_time_hours"),
            "forecast_expected_ret": (strat_dir.get("expected_return_by_horizon") or {}).get("7d"),
            "p_profit": strat_dir.get("p_profit"),
            "hold_duration": composite.get("hold_duration"),
        }
        reason_codes = reasons or [action.replace(" ", "_")]
        return {
            "action": action,
            "responsible_channel": str(composite.get("strategy_type") or "strategy_matrix"),
            "reason_codes": reason_codes,
            "reason_codes_csv": _csv(reason_codes),
            "blockers": blockers,
            "blockers_csv": _csv(blockers),
            "formula_inputs": formula_inputs,
            "confidence": composite.get("confidence"),
            "model_status": f"strategy_matrix:{strategy.get('rule_version', 'unknown')}",
            "probability_kind": "validated_directional"
            if composite.get("investable_label") == "INVESTABLE"
            else "strategy_matrix",
            "explanation": str(composite.get("explanation") or "Strategy matrix assigned the final action."),
        }

    flip = record.get("flip") or {}
    upgrade = record.get("upgrade") or {}
    forecast = record.get("forecast") or {}
    verdict = forecast.get("verdict") if isinstance(forecast.get("verdict"), dict) else {}
    verdict_status = verdict.get("status") or _verdict_from_record(record)
    flip_reasons = _listify(flip.get("reason_codes") or flip.get("reason_codes_csv"))
    upgrade_reasons = _listify(upgrade.get("reason_codes") or upgrade.get("reason_codes_csv"))
    forecast_failed = _listify(verdict.get("failed_csv"))
    flip_failed = _listify(flip.get("failed_gates") or flip.get("failed_gates_csv"))
    market_blockers = [
        code
        for code in flip_reasons
        if code
        in {
            "MISSING_BUY_PRICE",
            "MISSING_SELL_PRICE",
            "NON_EXECUTABLE_BOOK",
            "LIQUIDITY_UNAVAILABLE",
            "LIQUIDITY_BELOW_FLOOR",
        }
    ]
    formula = forecast.get("formula") if isinstance(forecast.get("formula"), dict) else {}
    formula_inputs = {
        "sell_price": flip.get("sell_price"),
        "buy_price": flip.get("buy_price"),
        "after_tax_sale": flip.get("after_tax_sale"),
        "profit": flip.get("profit"),
        "roi": flip.get("roi"),
        "spread_pct": flip.get("spread_pct"),
        "liquidity_score": flip.get("liquidity_score"),
        "forecast_expected_ret": forecast.get("expected_ret") if verdict_status == "INVESTABLE" else None,
        "forecast_formula": formula.get("return_formula"),
        "p_cross_next_threshold": upgrade.get("p_cross_next_threshold"),
        "p_upgrade": upgrade.get("p_upgrade"),
        "p_downgrade": upgrade.get("p_downgrade"),
        "next_threshold": upgrade.get("next_threshold"),
        "new_rank": upgrade.get("new_rank"),
    }

    action = "HOLD"
    channel = "forecast"
    reason_codes: list[str] = []
    blockers: list[str] = []
    confidence: Any = None
    explanation = "No actionable flip or threshold edge was detected."

    if verdict_status == "NOT INVESTABLE":
        action = "ABSTAIN"
        channel = "forecast"
        reason_codes = ["FORECAST_GOVERNANCE_BLOCK", *forecast_failed]
        blockers = forecast_failed
        confidence = 0
        explanation = "Hard governance gates failed; no action verb is allowed."
    elif flip.get("action") == "NO TRADE":
        action = "NO TRADE"
        channel = "data_quality"
        reason_codes = ["FLIP_BLOCKED", *flip_reasons]
        blockers = _unique([*market_blockers, *flip_failed, *forecast_failed])
        confidence = 0
        explanation = "Executable flip trade is blocked by market-data, ROI, or liquidity gates."
    elif verdict_status == "OBSERVATIONAL ONLY":
        action = "WATCH"
        channel = "forecast"
        reason_codes = ["FORECAST_DIAGNOSTIC_ONLY", *forecast_failed]
        blockers = forecast_failed
        confidence = 0
        explanation = "Forecast diagnostics are directional only; no action verb is allowed."
    elif upgrade.get("action") == "SELL":
        action = "SELL"
        channel = "upgrade"
        reason_codes = ["DOWNGRADE_RISK_OVERRIDES_FLIP", *upgrade_reasons]
        blockers = forecast_failed
        confidence = upgrade.get("confidence")
        explanation = "Upgrade downgrade risk is the primary signal; any positive flip edge remains visible in the flip columns."
    elif flip.get("action") == "BUY":
        action = "BUY FLIP"
        channel = "flip"
        reason_codes = ["EXECUTABLE_FLIP_EDGE", *flip_reasons]
        blockers = forecast_failed
        confidence = 100
        explanation = "Executable bid/ask math clears price, ROI, and liquidity gates; forecast EV is diagnostic only."
    elif upgrade.get("action") == "BUY SPECULATIVE":
        if market_blockers:
            action = "NO TRADE"
            channel = "data_quality"
            reason_codes = ["UPGRADE_SIGNAL_BLOCKED_BY_MARKET_DATA", *upgrade_reasons, *flip_reasons]
            blockers = _unique([*market_blockers, *flip_failed, *forecast_failed])
            confidence = upgrade.get("confidence")
            explanation = "Upgrade scenario is positive, but missing or non-executable market data blocks a buy."
        else:
            action = "BUY SPECULATIVE"
            channel = "upgrade"
            reason_codes = ["SCENARIO_THRESHOLD_EDGE", *upgrade_reasons]
            blockers = forecast_failed
            confidence = upgrade.get("confidence")
            explanation = "Roster-threshold scenario supports a speculative buy; probabilities are scenario-based and uncalibrated."
    elif upgrade.get("action") == "WATCH":
        action = "WATCH"
        channel = "upgrade"
        reason_codes = ["UPGRADE_WATCH", *upgrade_reasons]
        blockers = _unique([*market_blockers, *forecast_failed])
        confidence = upgrade.get("confidence")
        explanation = "Upgrade scenario is informative but not strong enough for a buy."
    else:
        reason_codes = ["NO_ACTIONABLE_EDGE", *flip_reasons, *upgrade_reasons]

    model_statuses = _unique(
        [
            str(upgrade.get("model_status") or "uncalibrated_threshold_model"),
            "forecast_diagnostic_only" if forecast.get("diagnostic_only") else "",
        ]
    )
    reason_codes = _unique(reason_codes) or ["NO_ACTIONABLE_EDGE"]
    blockers = _unique(blockers)
    return {
        "action": action,
        "responsible_channel": channel,
        "reason_codes": reason_codes,
        "reason_codes_csv": _csv(reason_codes),
        "blockers": blockers,
        "blockers_csv": _csv(blockers),
        "formula_inputs": formula_inputs,
        "confidence": confidence,
        "model_status": ",".join(model_statuses),
        "probability_kind": str(upgrade.get("probability_kind") or "scenario"),
        "explanation": explanation,
    }


def enrich_scan_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Expose Shiny-era scan columns while preserving nested API payloads."""

    card = record.get("card") or {}
    flip = record.get("flip") or {}
    upgrade = record.get("upgrade") or {}
    forecast = record.get("forecast") or {}
    strategy = record.get("strategy") if isinstance(record.get("strategy"), dict) else {}
    composite = strategy.get("composite") if isinstance(strategy.get("composite"), dict) else {}
    strat_flip = strategy.get("flip") if isinstance(strategy.get("flip"), dict) else {}
    strat_dir = strategy.get("directional") if isinstance(strategy.get("directional"), dict) else {}
    strat_inv = strategy.get("inventory") if isinstance(strategy.get("inventory"), dict) else {}
    gates = forecast.get("gates") if isinstance(forecast.get("gates"), dict) else {}
    verdict = forecast.get("verdict") if isinstance(forecast.get("verdict"), dict) else {}
    validation = record.get("validation") if isinstance(record.get("validation"), dict) else {}
    if record.get("status") == "dropped":
        reason = record.get("reason") or "fetch_error"
        record["decision"] = _decision_for_record(record)
        record.update({
            "name": record.get("name") or "-",
            "scan_status": "INVALID",
            "verdict_status": "NOT INVESTABLE",
            "rarity": _first(record.get("rarity"), card.get("rarity")),
            "decision_tier": "UNRATED",
            "validation_tier": "UNRATED",
            "data_coverage_tier": "UNVALIDATED",
            "performance_validation_tier": "UNVALIDATED",
            "tier": "UNRATED",
            "flip_reason_codes": str(reason),
            "upgrade_reason_codes": "",
            "gates_failed_csv": str(reason),
            "forecast_direction": "FORECAST UNAVAILABLE",
            "forecast_ev_7d": None,
            "decision_action": record["decision"]["action"],
            "responsible_channel": record["decision"]["responsible_channel"],
            "decision_reason_codes": record["decision"]["reason_codes_csv"],
            "decision_blockers": record["decision"]["blockers_csv"],
            "model_status": record["decision"]["model_status"],
            "probability_kind": record["decision"]["probability_kind"],
        })
        return record

    decision = _decision_for_record(record)
    decision_tier = forecast.get("performance_validation_tier") or forecast.get("validation_tier") or forecast.get("tier") or "UNRATED"
    record["decision"] = decision
    record.update({
        "rarity": _first(card.get("rarity"), upgrade.get("rarity")),
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
        "forecast_ev_7d": forecast.get("expected_ret") if verdict.get("status") == "INVESTABLE" else None,
        "forecast_p_up_7d": forecast.get("p_profit"),
        "strategy_type": composite.get("strategy_type"),
        "final_action": composite.get("final_action"),
        "flip_verdict": strat_flip.get("verdict"),
        "directional_verdict": strat_dir.get("verdict"),
        "inventory_verdict": strat_inv.get("verdict"),
        "holding_horizon": composite.get("hold_duration"),
        "holding_instruction": composite.get("holding_instruction"),
        "entry_timing": composite.get("entry_timing"),
        "exit_timing": composite.get("exit_timing"),
        "max_hold_hours": composite.get("max_hold_hours"),
        "investable_label": composite.get("investable_label"),
        "inventory_risk_score": strat_inv.get("inventory_risk_score"),
        "expected_exit_time_hours": strat_inv.get("expected_exit_time_hours"),
        "forecast_formula": (forecast.get("formula") or {}).get("return_formula")
        if isinstance(forecast.get("formula"), dict)
        else None,
        "forecast_score": None,
        "forecast_action": "HOLD",
        "scan_status": _status_from_record(record),
        "verdict_status": _verdict_from_record(record),
        "decision_tier": decision_tier,
        "validation_tier": decision_tier,
        "data_coverage_tier": strat_dir.get("data_coverage_tier") or forecast.get("data_coverage_tier") or forecast.get("tier") or "UNRATED",
        "performance_validation_tier": strat_dir.get("performance_validation_tier") or decision_tier,
        "tier": decision_tier,
        "gates_failed_csv": verdict.get("failed_csv") or gates.get("failed_csv") or "",
        "validation_mismatch": validation.get("mismatch"),
        "decision_action": decision["action"],
        "responsible_channel": decision["responsible_channel"],
        "decision_reason_codes": decision["reason_codes_csv"],
        "decision_blockers": decision["blockers_csv"],
        "model_status": decision["model_status"],
        "probability_kind": decision["probability_kind"],
    })
    return record


def analyze_listing(
    listing: dict[str, Any],
    *,
    stats: dict[str, Any] | None = None,
    enrich_mlb_stats: bool = False,
    collect: bool = True,
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
    scored["strategy"] = build_strategy_record(scored, listing)
    scored["provenance"] = provenance_for_listing(
        listing,
        sample_size=scored["forecast"].get("n_prices"),
        validation_tier=((scored["strategy"].get("directional") or {}).get("validation_tier")),
        data_coverage_tier=((scored["strategy"].get("directional") or {}).get("data_coverage_tier")),
        performance_validation_tier=((scored["strategy"].get("directional") or {}).get("performance_validation_tier")),
        rule_version=scored["strategy"].get("rule_version"),
    )
    scored["collection_status"] = (
        collect_market_snapshot(listing, scored["strategy"])
        if collect
        else {"status": "skipped", "reason": "write token not supplied for public analysis request"}
    )
    scored["decision_channels"] = {
        "flip": scored["flip"]["action"],
        "upgrade": scored["upgrade"]["action"],
        "forecast": scored["forecast"].get("direction", "FORECAST UNAVAILABLE"),
    }
    enriched = enrich_scan_fields(scored)
    enriched["prediction_collection_status"] = (
        collect_model_prediction(enriched)
        if collect
        else {"status": "skipped", "reason": "write token not supplied for public analysis request"}
    )
    return enriched


def partition_scan(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Bucket scan records by final decision action."""
    buckets: dict[str, list[dict[str, Any]]] = {
        "flip_buys": [],
        "upgrade_buys": [],
        "watch": [],
        "holds": [],
        "sells": [],
        "no_trade": [],
        "observational": [],
        "dropped": [],
    }
    for rec in records:
        enrich_scan_fields(rec)
        if rec.get("status") == "dropped":
            buckets["dropped"].append(rec)
            continue
        action = (rec.get("decision") or {}).get("action") or rec.get("decision_action")
        if action in {"BUY FLIP", "INSTANT FLIP ONLY", "SPREAD CAPTURE ONLY", "FLIP OR SHORT HOLD"}:
            buckets["flip_buys"].append(rec)
        elif action in {"BUY SPECULATIVE", "SPECULATIVE HOLD"}:
            buckets["upgrade_buys"].append(rec)
        elif action == "SELL":
            buckets["sells"].append(rec)
        elif action in {"WATCH", "WATCHLIST / NO MODEL TRADE", "MANUAL REVIEW"}:
            buckets["watch"].append(rec)
        elif action in {"NO TRADE", "ABSTAIN", "AVOID", "AVOID / MANUAL REVIEW"}:
            buckets["no_trade"].append(rec)
        elif _verdict_from_record(rec) == "OBSERVATIONAL ONLY":
            buckets["observational"].append(rec)
        else:
            buckets["holds"].append(rec)

    buckets["flip_buys"].sort(key=lambda r: ((r.get("flip") or {}).get("roi") or -999), reverse=True)
    buckets["upgrade_buys"].sort(key=lambda r: ((r.get("upgrade") or {}).get("upgrade_score") or -999), reverse=True)
    buckets["sells"].sort(key=lambda r: ((r.get("flip") or {}).get("roi") or 999))
    buckets["observational"].sort(
        key=lambda r: ((r.get("forecast") or {}).get("expected_ret") or 0.0),
        reverse=True,
    )
    buckets["watch"].sort(key=lambda r: ((r.get("upgrade") or {}).get("upgrade_score") or 0.0), reverse=True)
    buckets["no_trade"].sort(key=lambda r: str(r.get("decision_blockers") or r.get("flip_reason_codes") or ""))
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
    tiers = Counter(str(row.get("decision_tier") or row.get("tier") or "UNRATED") for row in records if row.get("status") != "dropped")
    rarities = Counter(str(row.get("rarity") or (row.get("card") or {}).get("rarity") or "UNKNOWN") for row in records if row.get("status") != "dropped")
    spreads = [float(row["spread_pct"]) for row in records if isinstance(row.get("spread_pct"), (int, float))]
    liq = [float(row["liquidity_recent"]) for row in records if isinstance(row.get("liquidity_recent"), (int, float))]
    return {
        "tier_distribution": dict(tiers),
        "rarity_distribution": dict(rarities),
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
    collect = bool(payload.get("_persistence_authorized", False))
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
            "verdict": {
                "status": "OBSERVATIONAL ONLY",
                "failed": ["listing_required"],
                "failed_csv": "listing_required",
                "reasons": ["listing payload required for forecast diagnostics"],
            },
            "tier": "UNRATED",
        }
            scored["strategy"] = build_strategy_record(scored)
            scored["provenance"] = provenance_for_listing(
                None,
                sample_size=0,
                validation_tier="UNVALIDATED",
                data_coverage_tier="UNVALIDATED",
                performance_validation_tier="UNVALIDATED",
                rule_version=scored["strategy"].get("rule_version"),
            )
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
                collect=collect,
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
        "rarity_distribution": summary["rarity_distribution"],
        "market_health": summary["market_health"],
        "dropped_summary": summary["dropped_summary"],
    }

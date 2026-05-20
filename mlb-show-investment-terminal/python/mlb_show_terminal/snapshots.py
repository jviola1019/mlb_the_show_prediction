"""Historical roster-update snapshot and label pipeline."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .artifacts import flatten_score, score_row, write_json
from .historical import evaluate_backtest, read_records
from .mlb_stats import recent_vs_season
from .theshow import get_listing
from .upgrade import next_ovr_threshold
from .uuid_tools import parse_uuid_tokens


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _flatten_stats(row: dict[str, Any], prefix: str, stats: dict[str, Any]) -> None:
    for key, value in stats.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            row[f"{prefix}_{key}"] = value


def _with_nested_stats(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    if not isinstance(payload.get("recent"), dict):
        recent = {
            key.removeprefix("recent_"): value
            for key, value in payload.items()
            if key.startswith("recent_")
        }
        if recent:
            payload["recent"] = recent
    if not isinstance(payload.get("season"), dict):
        season = {
            key.removeprefix("season_"): value
            for key, value in payload.items()
            if key.startswith("season_")
        }
        if season:
            payload["season"] = season
    return payload


def listing_snapshot_row(
    listing: dict[str, Any],
    snapshot_id: str,
    captured_at: str,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = listing.get("item") or {}
    row = {
        "snapshot_id": snapshot_id,
        "captured_at": captured_at,
        "uuid": item.get("uuid"),
        "name": item.get("name") or listing.get("listing_name"),
        "rarity": item.get("rarity"),
        "ovr": item.get("ovr") or item.get("rank"),
        "new_rank": item.get("new_rank"),
        "team": item.get("team"),
        "raw_ask": listing.get("best_sell_price"),
        "raw_bid": listing.get("best_buy_price"),
    }
    if stats:
        row["role"] = stats.get("role", "hitter")
        recent = stats.get("recent") if isinstance(stats.get("recent"), dict) else {}
        season = stats.get("season") if isinstance(stats.get("season"), dict) else {}
        _flatten_stats(row, "recent", recent)
        _flatten_stats(row, "season", season)
    return row


def snapshot_live_cards(
    uuids: Iterable[str],
    *,
    snapshot_id: str,
    year: int = 26,
    enrich_mlb_stats: bool = False,
) -> list[dict[str, Any]]:
    captured_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for uuid in parse_uuid_tokens(list(uuids)).uuids:
        listing = get_listing(uuid, year=year)
        stats = None
        if enrich_mlb_stats:
            item = listing.get("item") or {}
            name = item.get("name") or listing.get("listing_name")
            if name:
                try:
                    stats = recent_vs_season(str(name))
                except Exception:
                    stats = None
        rows.append(listing_snapshot_row(listing, snapshot_id, captured_at, stats=stats))
    return rows


def build_upgrade_labels(pre_rows: Iterable[dict[str, Any]], post_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    post_by_uuid = {str(row.get("uuid")).lower(): row for row in post_rows if row.get("uuid")}
    labels: list[dict[str, Any]] = []
    for pre in pre_rows:
        uuid = str(pre.get("uuid") or "").lower()
        post = post_by_uuid.get(uuid)
        if not post:
            continue
        pre_ovr = _num(pre.get("ovr") or pre.get("current_ovr"))
        post_ovr = _num(post.get("ovr") or post.get("current_ovr"))
        threshold = next_ovr_threshold(pre_ovr, pre.get("rarity"))
        crossed = bool(pre_ovr is not None and post_ovr is not None and threshold is not None and pre_ovr < threshold <= post_ovr)
        labels.append({
            "uuid": uuid,
            "name": pre.get("name") or post.get("name"),
            "pre_ovr": pre_ovr,
            "post_ovr": post_ovr,
            "pre_rarity": pre.get("rarity"),
            "post_rarity": post.get("rarity"),
            "next_threshold": threshold,
            "ovr_delta": None if pre_ovr is None or post_ovr is None else post_ovr - pre_ovr,
            "upgraded": bool(pre_ovr is not None and post_ovr is not None and post_ovr > pre_ovr),
            "downgraded": bool(pre_ovr is not None and post_ovr is not None and post_ovr < pre_ovr),
            "crossed_next_threshold": crossed,
        })
    return labels


def score_snapshot(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        payload = _with_nested_stats(row)
        payload["current_ovr"] = payload.get("current_ovr") or payload.get("ovr")
        scored.append(flatten_score(score_row(payload)))
    return scored


def backfill_upgrade_pair(
    pre_rows: Iterable[dict[str, Any]],
    post_rows: Iterable[dict[str, Any]],
    *,
    n_bins: int = 5,
    decision_threshold: float = 0.50,
    min_n: int = 30,
    min_events: int = 1,
) -> dict[str, Any]:
    """Score a historical pre-update snapshot and evaluate against post labels.

    This is the offline historical backfill path. It never fabricates outcomes:
    ``post_rows`` must contain the real post-update OVR/rarity state for the
    same UUIDs. Predictions are scored from the pre-update snapshot only.
    """

    pre = [dict(row) for row in pre_rows]
    post = [dict(row) for row in post_rows]
    predictions = score_snapshot(pre)
    labels = build_upgrade_labels(pre, post)
    backtest = evaluate_backtest(
        predictions,
        labels,
        prob_col="upgrade_p_cross_next_threshold",
        decision_threshold=decision_threshold,
        n_bins=n_bins,
        min_n=min_n,
        min_events=min_events,
    )
    return {
        "status": "available" if backtest.get("status") == "available" else "unavailable",
        "counts": {
            "pre_rows": len(pre),
            "post_rows": len(post),
            "predictions": len(predictions),
            "labels": len(labels),
            "matched": backtest.get("n", 0),
        },
        "predictions": predictions,
        "labels": labels,
        "backtest": backtest,
    }


def write_records_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def backtest_upgrade_files(
    predictions_path: str | Path,
    labels_path: str | Path,
    *,
    n_bins: int = 5,
    decision_threshold: float = 0.50,
    min_n: int = 30,
    min_events: int = 1,
) -> dict[str, Any]:
    return evaluate_backtest(
        read_records(predictions_path),
        read_records(labels_path),
        prob_col="upgrade_p_cross_next_threshold",
        decision_threshold=decision_threshold,
        n_bins=n_bins,
        min_n=min_n,
        min_events=min_events,
    )


def read_csv_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_backfill_outputs(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    write_records_csv(out / "predictions.csv", payload.get("predictions", []))
    write_records_csv(out / "labels.csv", payload.get("labels", []))
    write_json(out / "backtest.json", payload.get("backtest", {}))
    write_json(out / "summary.json", {
        "status": payload.get("status"),
        "counts": payload.get("counts", {}),
    })

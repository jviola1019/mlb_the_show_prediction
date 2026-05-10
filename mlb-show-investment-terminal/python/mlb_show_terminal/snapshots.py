"""Historical roster-update snapshot and label pipeline."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .artifacts import flatten_score, score_row
from .historical import evaluate_backtest, read_records
from .theshow import get_listing
from .upgrade import next_ovr_threshold
from .uuid_tools import parse_uuid_tokens


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def listing_snapshot_row(listing: dict[str, Any], snapshot_id: str, captured_at: str) -> dict[str, Any]:
    item = listing.get("item") or {}
    return {
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


def snapshot_live_cards(uuids: Iterable[str], *, snapshot_id: str, year: int = 26) -> list[dict[str, Any]]:
    captured_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for uuid in parse_uuid_tokens(list(uuids)).uuids:
        rows.append(listing_snapshot_row(get_listing(uuid, year=year), snapshot_id, captured_at))
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
        payload = dict(row)
        payload["current_ovr"] = payload.get("current_ovr") or payload.get("ovr")
        scored.append(flatten_score(score_row(payload)))
    return scored


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


def backtest_upgrade_files(predictions_path: str | Path, labels_path: str | Path, *, n_bins: int = 5) -> dict[str, Any]:
    return evaluate_backtest(read_records(predictions_path), read_records(labels_path), n_bins=n_bins)


def read_csv_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]

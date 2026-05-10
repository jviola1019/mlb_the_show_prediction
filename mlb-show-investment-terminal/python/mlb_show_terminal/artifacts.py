"""Deterministic Python artifacts for the Shiny UI shell."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .market import compute_flip, validate_flip_formula
from .upgrade import score_upgrade


def _first(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] not in {None, ""}:
            return row[name]
    return default


def _nested(row: dict[str, Any], name: str) -> dict[str, Any]:
    value = row.get(name)
    return value if isinstance(value, dict) else {}


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    """Score one listing/card row using the Python engines."""

    ask = _first(row, "raw_ask", "ask", "best_sell_price", "sell_price")
    bid = _first(row, "raw_bid", "bid", "best_buy_price", "buy_price")
    flip = compute_flip(
        sell_price=ask,
        buy_price=bid,
        liquidity_score=_first(row, "liquidity_score"),
        liquidity_n=_first(row, "liquidity_n", default=0),
        liquidity_recent=_first(row, "liquidity_recent"),
    )

    recent = _nested(row, "recent")
    season = _nested(row, "season")
    upgrade = score_upgrade(
        recent=recent,
        season=season,
        role=str(_first(row, "role", default="hitter")),
        current_ovr=_first(row, "current_ovr", "ovr"),
        rarity=_first(row, "rarity"),
        new_rank=_first(row, "new_rank"),
    )

    return {
        "python_backend": True,
        "uuid": row.get("uuid"),
        "name": row.get("name"),
        "flip": flip.to_dict(),
        "upgrade": upgrade.to_dict(),
        "validation": validate_flip_formula(ask, bid, engine=flip),
    }


def score_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [score_row(dict(row)) for row in rows]


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def flatten_score(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "python_backend": row.get("python_backend", True),
        "uuid": row.get("uuid"),
        "name": row.get("name"),
    }
    for prefix in ("flip", "upgrade"):
        payload = row.get(prefix) or {}
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            flat[f"{prefix}_{key}"] = value
    return flat


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    flat_rows = [flatten_score(row) for row in rows]
    if not flat_rows:
        p.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in flat_rows for key in row})
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)

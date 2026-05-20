"""Execution ledger helpers for realized edge tracking."""

from __future__ import annotations

import csv
import io
import time
from typing import Any

from .persistence import write_table


REQUIRED_FIELDS = {"card_uuid", "buy_price", "timestamp", "strategy_type"}


def validate_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_FIELDS if row.get(field) in (None, ""))
    return {
        "valid": not missing,
        "missing": missing,
        "server_timestamp": _utc_now(),
    }


def realized_trade_metrics(rows: list[dict[str, Any]], *, tax_rate: float = 0.10) -> dict[str, Any]:
    closed: list[dict[str, float]] = []
    failed = 0
    for row in rows:
        buy = _num(row.get("buy_price"))
        sell = _num(row.get("sell_price") or row.get("exit_price"))
        if str(row.get("fill_status") or "").lower() in {"failed", "expired"}:
            failed += 1
        if buy is None or buy <= 0 or sell is None:
            continue
        net = sell * (1 - tax_rate) - buy - (_num(row.get("slippage")) or 0)
        closed.append({"net": net, "roi": net / buy, "expected": _num(row.get("expected_net_stubs")) or 0})
    total = sum(t["net"] for t in closed)
    expected = sum(t["expected"] for t in closed)
    return {
        "status": "ok",
        "closed_trades": len(closed),
        "realized_profit": total,
        "realized_roi": (sum(t["roi"] for t in closed) / len(closed)) if closed else None,
        "expected_vs_realized_stubs": total - expected if closed else None,
        "average_edge_decay": ((expected - total) / expected) if expected else None,
        "failed_exit_rate": failed / len(rows) if rows else None,
        "model_overconfidence_score": max(0.0, expected - total) if closed else None,
    }


def persist_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    validation = validate_ledger_row(row)
    if not validation["valid"]:
        return {"status": "invalid", **validation}
    payload = dict(row)
    payload.setdefault("timestamp", _utc_now())
    payload["validation"] = validation
    return write_table("execution_ledger", payload)


def ledger_rows_from_csv(text: str) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(text)))


def ledger_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    fields = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

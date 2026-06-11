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
    closed: list[dict[str, Any]] = []
    failed = 0
    open_positions = 0
    cancelled = 0
    fill_minutes: list[float] = []
    hold_hours: list[float] = []
    by_strategy: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        buy = _num(row.get("buy_price"))
        sell = _num(row.get("sell_price") or row.get("exit_price"))
        status = str(row.get("fill_status") or "").lower()
        strategy = str(row.get("strategy_type") or "unknown")
        if status in {"failed", "expired"}:
            failed += 1
        if status in {"cancelled", "canceled"}:
            cancelled += 1
        if status in {"open", "pending", "listed"} and sell is None:
            open_positions += 1
        fill = _num(row.get("time_to_fill_minutes"))
        holding = _num(row.get("holding_time_hours"))
        if fill is not None:
            fill_minutes.append(fill)
        if holding is not None:
            hold_hours.append(holding)
        if buy is None or buy <= 0 or sell is None:
            continue
        row_tax = _num(row.get("tax_rate"))
        if row_tax is None:
            row_tax = _num(row.get("tax"))
        if row_tax is None:
            row_tax = tax_rate
        if row_tax > 1:
            row_tax = row_tax / 100.0
        net = sell * (1 - row_tax) - buy - (_num(row.get("slippage")) or 0)
        item = {"net": net, "roi": net / buy, "expected": _num(row.get("expected_net_stubs")) or 0}
        closed.append(item)
        by_strategy.setdefault(strategy, []).append(item)
    total = sum(t["net"] for t in closed)
    expected = sum(t["expected"] for t in closed)
    by_strategy_summary = {
        strategy: {
            "closed_trades": len(items),
            "realized_profit": sum(t["net"] for t in items),
            "realized_roi": sum(t["roi"] for t in items) / len(items) if items else None,
            "expected_net_stubs": sum(t["expected"] for t in items),
        }
        for strategy, items in sorted(by_strategy.items())
    }
    return {
        "status": "ok",
        "rows": len(rows),
        "closed_trades": len(closed),
        "open_positions": open_positions,
        "failed_exits": failed,
        "cancelled_orders": cancelled,
        "realized_profit": total,
        "realized_roi": (sum(t["roi"] for t in closed) / len(closed)) if closed else None,
        "expected_vs_realized_stubs": total - expected if closed else None,
        "average_edge_decay": ((expected - total) / expected) if expected else None,
        "failed_exit_rate": failed / len(rows) if rows else None,
        "average_time_to_fill_minutes": sum(fill_minutes) / len(fill_minutes) if fill_minutes else None,
        "average_holding_time_hours": sum(hold_hours) / len(hold_hours) if hold_hours else None,
        "model_overconfidence_score": max(0.0, expected - total) if closed else None,
        "by_strategy": by_strategy_summary,
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

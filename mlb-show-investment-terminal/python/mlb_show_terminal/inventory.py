"""Inventory and liquidity quality scoring.

The score is deliberately conservative and uses only observable market fields
already present in the live listing/scan payload. It does not invent completed
transactions or historical exits.
"""

from __future__ import annotations

import math
from typing import Any

from .strategy_ontology import InventoryStrategy, InventoryVerdict


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def score_inventory(
    *,
    liquidity_score: Any = None,
    liquidity_recent: Any = None,
    liquidity_n: Any = None,
    spread_pct: Any = None,
    freshness_failed: bool = False,
) -> InventoryStrategy:
    """Return a deterministic inventory verdict from observable liquidity.

    ``inventory_risk_score`` is 0..1 where 1 is worst. Expected exit time and
    position size are risk controls, not realized historical claims.
    """
    score = _num(liquidity_score)
    recent = _int(liquidity_recent)
    n = _int(liquidity_n)
    spread = _num(spread_pct)

    reasons: list[str] = []
    passed: list[str] = []
    failed: list[str] = []

    if freshness_failed:
        reasons.append("STALE_SOURCE")
        failed.append("freshness")
    else:
        passed.append("freshness")

    if recent is None and n is not None and n > 0:
        recent = n
    if score is None and recent is not None:
        score = max(0.0, min(1.0, recent / 150.0))

    if score is None and recent is None:
        verdict = InventoryVerdict.THIN
        risk = 0.82
        reasons.append("LIQUIDITY_UNAVAILABLE")
        failed.append("liquidity")
    elif freshness_failed:
        verdict = InventoryVerdict.DEAD_INVENTORY
        risk = 1.0
    elif (recent is not None and recent <= 0) or (score is not None and score <= 0.02):
        verdict = InventoryVerdict.DEAD_INVENTORY
        risk = 0.98
        reasons.append("NO_RECENT_MARKET_ACTIVITY")
        failed.append("liquidity")
    elif (recent is not None and recent >= 100) or (score is not None and score >= 0.66):
        verdict = InventoryVerdict.HIGH_LIQUIDITY
        risk = 0.18
        reasons.append("HIGH_RECENT_ACTIVITY")
        passed.append("liquidity")
    elif (recent is not None and recent >= 30) or (score is not None and score >= 0.25):
        verdict = InventoryVerdict.MEDIUM_LIQUIDITY
        risk = 0.38
        reasons.append("ADEQUATE_RECENT_ACTIVITY")
        passed.append("liquidity")
    else:
        verdict = InventoryVerdict.THIN
        risk = 0.70
        reasons.append("THIN_RECENT_ACTIVITY")
        failed.append("liquidity")

    if spread is not None and spread >= 0.35:
        risk = min(1.0, risk + 0.14)
        reasons.append("WIDE_SPREAD_EXIT_RISK")
        failed.append("spread_width")
    elif spread is not None:
        passed.append("spread_width")

    if verdict == InventoryVerdict.HIGH_LIQUIDITY:
        exit_hours = 2.0
        cap = 25000
        sizing = "normal size; exit gate still controls hold duration"
    elif verdict == InventoryVerdict.MEDIUM_LIQUIDITY:
        exit_hours = 8.0
        cap = 10000
        sizing = "reduced size; prefer faster exits"
    elif verdict == InventoryVerdict.THIN:
        exit_hours = 24.0
        cap = 2500
        sizing = "micro size only; manual review before entry"
    else:
        exit_hours = None
        cap = 0
        sizing = "no new position"

    warning = None
    if verdict == InventoryVerdict.DEAD_INVENTORY:
        warning = "dead-inventory protection active; do not enter without manual review"
    elif verdict == InventoryVerdict.THIN:
        warning = "thin liquidity; exit may require undercutting or long queue time"

    return InventoryStrategy(
        verdict=verdict,
        inventory_risk_score=round(risk, 4),
        expected_exit_time_hours=exit_hours,
        liquidity_score=score,
        liquidity_recent=recent,
        dead_inventory_warning=warning,
        position_size_recommendation=sizing,
        max_position_stubs=cap,
        reason_codes=list(dict.fromkeys(reasons)),
        gates_passed=list(dict.fromkeys(passed)),
        gates_failed=list(dict.fromkeys(failed)),
    )

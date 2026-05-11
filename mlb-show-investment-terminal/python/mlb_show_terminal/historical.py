"""Historical roster-update backtest utilities.

The functions in this module never infer or fabricate labels. A backtest is
available only when explicit historical outcomes are supplied by file or by the
caller.
"""

from __future__ import annotations

import csv
import json
from math import isfinite
from pathlib import Path
from typing import Any, Iterable


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if isfinite(out) else None


def _bool_label(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)) and isfinite(float(value)):
        if float(value) in {0.0, 1.0}:
            return bool(int(value))
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "upgraded", "crossed"}:
        return True
    if text in {"0", "false", "f", "no", "n", "unchanged", "downgraded", "not_crossed"}:
        return False
    return None


def read_records(path: str | Path | None) -> list[dict[str, Any]]:
    """Read JSON or CSV records.

    Supported JSON shapes are either a list of objects or an object with a
    top-level ``records`` list. CSV files are read through DictReader.
    """

    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        return []
    if p.suffix.lower() == ".json":
        payload = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            payload = payload.get("records", [])
        return [dict(row) for row in payload if isinstance(row, dict)]
    with p.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_codes": [reason],
        "reason_codes_csv": reason,
        "n": 0,
        "brier_score": None,
        "precision": None,
        "recall": None,
        "calibration_curve": [],
    }


def merge_predictions_labels(
    predictions: Iterable[dict[str, Any]],
    labels: Iterable[dict[str, Any]],
    *,
    id_col: str = "uuid",
    prob_col: str = "p_cross_next_threshold",
    outcome_col: str = "crossed_next_threshold",
) -> list[dict[str, Any]]:
    label_map = {
        str(row.get(id_col)): row
        for row in labels
        if row.get(id_col) not in {None, ""}
    }
    merged: list[dict[str, Any]] = []
    for pred in predictions:
        key = pred.get(id_col)
        if key in {None, ""}:
            continue
        label = label_map.get(str(key))
        if label is None:
            continue
        prob = _num(pred.get(prob_col))
        outcome = _bool_label(label.get(outcome_col))
        if prob is None or outcome is None:
            continue
        merged.append({"id": str(key), "prob": max(0.0, min(1.0, prob)), "outcome": outcome})
    return merged


def evaluate_backtest(
    predictions: Iterable[dict[str, Any]] | None,
    labels: Iterable[dict[str, Any]] | None = None,
    *,
    id_col: str = "uuid",
    prob_col: str = "p_cross_next_threshold",
    outcome_col: str = "crossed_next_threshold",
    decision_threshold: float = 0.50,
    n_bins: int = 5,
) -> dict[str, Any]:
    """Evaluate threshold prediction calibration with real labels.

    Returns an unavailable payload unless both prediction rows and explicit
    historical labels are present.
    """

    predictions = list(predictions or [])
    labels = list(labels or [])
    if not predictions:
        return _unavailable("PREDICTIONS_UNAVAILABLE")
    if not labels:
        return _unavailable("HISTORICAL_LABELS_UNAVAILABLE")

    rows = merge_predictions_labels(
        predictions,
        labels,
        id_col=id_col,
        prob_col=prob_col,
        outcome_col=outcome_col,
    )
    if not rows:
        return _unavailable("NO_MATCHED_HISTORICAL_LABELS")

    y = [1 if row["outcome"] else 0 for row in rows]
    p = [row["prob"] for row in rows]
    n = len(rows)
    brier = sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / n
    pred_pos = [pi >= decision_threshold for pi in p]
    tp = sum(1 for flag, yi in zip(pred_pos, y) if flag and yi == 1)
    fp = sum(1 for flag, yi in zip(pred_pos, y) if flag and yi == 0)
    fn = sum(1 for flag, yi in zip(pred_pos, y) if (not flag) and yi == 1)
    precision = tp / (tp + fp) if tp + fp > 0 else None
    recall = tp / (tp + fn) if tp + fn > 0 else None

    n_bins = max(1, int(n_bins))
    bins: list[dict[str, Any]] = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if i == n_bins - 1:
            idx = [j for j, pi in enumerate(p) if lo <= pi <= hi]
        else:
            idx = [j for j, pi in enumerate(p) if lo <= pi < hi]
        if not idx:
            continue
        bins.append(
            {
                "bin": i + 1,
                "prob_lo": lo,
                "prob_hi": hi,
                "n": len(idx),
                "mean_predicted": sum(p[j] for j in idx) / len(idx),
                "observed_rate": sum(y[j] for j in idx) / len(idx),
            }
        )

    return {
        "status": "available",
        "reason_codes": ["REAL_HISTORICAL_LABELS"],
        "reason_codes_csv": "REAL_HISTORICAL_LABELS",
        "n": n,
        "brier_score": brier,
        "precision": precision,
        "recall": recall,
        "calibration_curve": bins,
    }

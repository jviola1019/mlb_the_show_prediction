"""Historical roster-update backtest utilities.

The functions in this module never infer or fabricate labels. A backtest is
available only when explicit historical outcomes are supplied by file or by the
caller.
"""

from __future__ import annotations

import csv
import json
from math import isfinite, log
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PROB_FALLBACKS = (
    "p_cross_next_threshold",
    "upgrade_p_cross_next_threshold",
    "p_upgrade",
    "upgrade_p_upgrade",
)
DEFAULT_OUTCOME_FALLBACKS = (
    "crossed_next_threshold",
    "upgrade_crossed_next_threshold",
)


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


def _first_num(row: dict[str, Any], names: Iterable[str]) -> float | None:
    for name in names:
        value = _num(row.get(name))
        if value is not None:
            return value
    return None


def _first_bool(row: dict[str, Any], names: Iterable[str]) -> bool | None:
    for name in names:
        value = _bool_label(row.get(name))
        if value is not None:
            return value
    return None


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float | None]:
    if total <= 0:
        return [None, None]
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = z * ((phat * (1 - phat) + z * z / (4 * total)) / total) ** 0.5 / denom
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


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


def _unavailable(reason: str, *, n: int = 0) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_codes": [reason],
        "reason_codes_csv": reason,
        "n": n,
        "matched_n": n,
        "decision_threshold": None,
        "base_rate": None,
        "brier_score": None,
        "brier_baseline": None,
        "brier_skill_score": None,
        "log_loss": None,
        "accuracy": None,
        "precision": None,
        "precision_ci": [None, None],
        "recall": None,
        "recall_ci": [None, None],
        "expected_calibration_error": None,
        "confusion": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
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
        prob_names = [prob_col]
        for fallback in DEFAULT_PROB_FALLBACKS:
            if fallback not in prob_names:
                prob_names.append(fallback)
        outcome_names = [outcome_col]
        for fallback in DEFAULT_OUTCOME_FALLBACKS:
            if fallback not in outcome_names:
                outcome_names.append(fallback)
        prob = _first_num(pred, prob_names)
        outcome = _first_bool(label, outcome_names)
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
    min_n: int = 30,
    min_events: int = 1,
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
    if n < max(1, int(min_n)):
        return _unavailable("INSUFFICIENT_HISTORICAL_LABELS", n=n)
    positives = sum(y)
    negatives = n - positives
    if positives < int(min_events) or negatives < int(min_events):
        return _unavailable("SINGLE_CLASS_HISTORICAL_LABELS", n=n)
    brier = sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / n
    base_rate = sum(y) / n
    brier_baseline = sum((base_rate - yi) ** 2 for yi in y) / n
    brier_skill_score = 1 - (brier / brier_baseline) if brier_baseline > 0 else None
    eps = 1e-12
    log_loss = -sum(
        yi * log(min(1 - eps, max(eps, pi)))
        + (1 - yi) * log(min(1 - eps, max(eps, 1 - pi)))
        for pi, yi in zip(p, y)
    ) / n
    pred_pos = [pi >= decision_threshold for pi in p]
    tp = sum(1 for flag, yi in zip(pred_pos, y) if flag and yi == 1)
    fp = sum(1 for flag, yi in zip(pred_pos, y) if flag and yi == 0)
    fn = sum(1 for flag, yi in zip(pred_pos, y) if (not flag) and yi == 1)
    tn = sum(1 for flag, yi in zip(pred_pos, y) if (not flag) and yi == 0)
    precision = tp / (tp + fp) if tp + fp > 0 else None
    recall = tp / (tp + fn) if tp + fn > 0 else None
    accuracy = (tp + tn) / n
    precision_ci = _wilson_interval(tp, tp + fp)
    recall_ci = _wilson_interval(tp, tp + fn)

    n_bins = max(1, int(n_bins))
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if i == n_bins - 1:
            idx = [j for j, pi in enumerate(p) if lo <= pi <= hi]
        else:
            idx = [j for j, pi in enumerate(p) if lo <= pi < hi]
        if not idx:
            continue
        mean_predicted = sum(p[j] for j in idx) / len(idx)
        observed_rate = sum(y[j] for j in idx) / len(idx)
        abs_error = abs(mean_predicted - observed_rate)
        ece += (len(idx) / n) * abs_error
        bins.append(
            {
                "bin": i + 1,
                "prob_lo": lo,
                "prob_hi": hi,
                "n": len(idx),
                "mean_predicted": mean_predicted,
                "observed_rate": observed_rate,
                "abs_calibration_error": abs_error,
            }
        )

    return {
        "status": "available",
        "reason_codes": ["REAL_HISTORICAL_LABELS"],
        "reason_codes_csv": "REAL_HISTORICAL_LABELS",
        "n": n,
        "decision_threshold": decision_threshold,
        "base_rate": base_rate,
        "brier_score": brier,
        "brier_baseline": brier_baseline,
        "brier_skill_score": brier_skill_score,
        "log_loss": log_loss,
        "accuracy": accuracy,
        "precision": precision,
        "precision_ci": precision_ci,
        "recall": recall,
        "recall_ci": recall_ci,
        "expected_calibration_error": ece,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "calibration_curve": bins,
    }

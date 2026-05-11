"""Static audit helpers for formulas and engine boundaries.

After the Shiny sunset, "parity" means Python <-> React feature parity.
There is no R reference any more; the Python backend is the single source
of truth for quant and the React frontend is the single UI.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any


PATTERNS = {
    "ev": re.compile(r"\bcompute_ev\b|expected_ret|ev_7d|forecast_ev", re.IGNORECASE),
    "spread": re.compile(r"spread_pct|spread|best_sell_price|best_buy_price", re.IGNORECASE),
    "tax": re.compile(r"tax_rate|after_tax", re.IGNORECASE),
    "flip": re.compile(r"compute_flip|after_tax_sale|profit / bid", re.IGNORECASE),
    "upgrade": re.compile(r"score_upgrade|p_cross|distance_to", re.IGNORECASE),
    "governance": re.compile(r"validation_gates|gating_verdict|7-gate|INVESTABLE|OBSERVATIONAL", re.IGNORECASE),
}


def audit_repo(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    hits: list[dict[str, Any]] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".py", ".ts", ".tsx"}:
            continue
        rel = str(path.relative_to(root_path))
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, start=1):
            tags = [name for name, pat in PATTERNS.items() if pat.search(line)]
            if tags:
                hits.append({"file": rel, "line": idx, "tags": tags, "text": line.strip()})

    findings = [
        {
            "id": "FORECAST_EV_IS_NOT_FLIP_EV",
            "status": "fixed_by_python_boundary",
            "detail": "Price forecasts remain diagnostics; executable flips use bid/ask after-tax math.",
        },
        {
            "id": "HISTORICAL_LABELS_REQUIRED",
            "status": "enforced",
            "detail": "Backtest metrics return unavailable unless explicit labels are supplied.",
        },
    ]
    return {"status": "ok", "files_scanned": len({h["file"] for h in hits}), "hits": hits, "findings": findings}


PARITY_FEATURES = [
    {
        "feature_id": "market_scan.partitions",
        "group": "Market Scan",
        "react_source": "frontend/src/tabs/ScanTab.tsx",
        "python_source": "python/mlb_show_terminal/scan.py::partition_scan",
        "tests": ["python/tests/test_api.py", "frontend/src/components.test.tsx"],
        "required_terms": ["flip_buys", "upgrade_buys", "holds", "sells", "observational", "dropped"],
    },
    {
        "feature_id": "market_scan.partition_columns",
        "group": "Market Scan",
        "react_source": "frontend/src/components.tsx",
        "python_source": "python/mlb_show_terminal/scan.py::enrich_scan_fields",
        "tests": ["frontend/src/components.test.tsx"],
        "required_terms": ["after_tax_sale", "flip_roi", "p_cross_next_threshold", "gates_failed_csv"],
    },
    {
        "feature_id": "market_scan.progress_jobs",
        "group": "Market Scan",
        "react_source": "frontend/src/tabs/ScanTab.tsx",
        "python_source": "python/mlb_show_terminal/scan_jobs.py",
        "tests": ["python/tests/test_api.py"],
        "required_terms": ["current_uuid", "current_name", "dropped_count", "invalid_count"],
    },
    {
        "feature_id": "market_scan.uuid_parser",
        "group": "Market Scan",
        "react_source": "frontend/src/uuid.ts",
        "python_source": "python/mlb_show_terminal/uuid_tools.py",
        "tests": ["frontend/src/uuid.test.ts"],
        "required_terms": ["duplicates", "invalid_tokens", "lower"],
    },
    {
        "feature_id": "card.forecast_cone",
        "group": "Card Analysis",
        "react_source": "frontend/src/tabs/CardTab.tsx",
        "python_source": "python/mlb_show_terminal/forecast.py::forecast_cone",
        "tests": ["python/tests/test_api.py"],
        "required_terms": ["cone", "p5", "p50", "p95"],
    },
    {
        "feature_id": "card.walk_forward_cv",
        "group": "Card Analysis",
        "react_source": "frontend/src/tabs/CardTab.tsx",
        "python_source": "python/mlb_show_terminal/forecast.py::walk_forward_cv",
        "tests": ["python/tests/test_api.py"],
        "required_terms": ["brier_point", "ic_point", "hit_rate"],
    },
    {
        "feature_id": "card.governance",
        "group": "Card Analysis",
        "react_source": "frontend/src/verdictGuard.tsx",
        "python_source": "python/mlb_show_terminal/governance.py::validation_gates",
        "tests": ["python/tests/test_governance.py"],
        "required_terms": ["INVESTABLE", "OBSERVATIONAL ONLY", "NOT INVESTABLE", "schema_valid", "calibration_present"],
    },
    {
        "feature_id": "validate.manual_flip",
        "group": "Validate",
        "react_source": "frontend/src/tabs/ValidateTab.tsx",
        "python_source": "python/mlb_show_terminal/market.py::validate_flip_formula",
        "tests": ["python/tests/test_market.py"],
        "required_terms": ["manual_after_tax_sale", "manual_roi", "mismatch"],
    },
    {
        "feature_id": "overall.market_health",
        "group": "Overall",
        "react_source": "frontend/src/tabs/OverallTab.tsx",
        "python_source": "python/mlb_show_terminal/scan.py::_scan_summary",
        "tests": ["python/tests/test_api.py"],
        "required_terms": ["market_health", "tier_distribution"],
    },
    {
        "feature_id": "viz.three_d",
        "group": "Visualization",
        "react_source": "frontend/src/viz/ForecastSurface3D.tsx",
        "python_source": "python/mlb_show_terminal/forecast.py::forecast_cone",
        "tests": ["frontend/src/components.test.tsx"],
        "required_terms": ["ForecastSurface3D", "react-three", "cone", "p95"],
    },
]


def _read_joined(root: Path, paths: list[str]) -> str:
    chunks: list[str] = []
    for rel in paths:
        path = root / rel
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def audit_parity(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root)
    rows: list[dict[str, Any]] = []
    for feature in PARITY_FEATURES:
        sources = [feature["react_source"].split("::")[0], feature["python_source"].split("::")[0]]
        text = _read_joined(root_path, sources)
        present = [term for term in feature["required_terms"] if term in text]
        if len(present) == len(feature["required_terms"]):
            status = "parity"
        elif present:
            status = "partial"
        else:
            status = "missing"
        rows.append({
            **feature,
            "status": status,
            "matched_terms": present,
            "notes": "Generated static parity check; behavior is verified by the listed tests.",
        })
    counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("parity", "partial", "missing")}
    return {
        "status": "ok" if counts["missing"] == 0 else "needs_attention",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "counts": counts,
        "features": rows,
    }


def parity_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Python <-> React Parity Audit",
        "",
        f"Generated: {payload.get('generated_at', '-')}",
        f"Status: {payload.get('status', '-')}",
        "",
        "| Feature | Group | Status | React | Python |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("features", []):
        lines.append(
            f"| {row['feature_id']} | {row['group']} | {row['status']} | "
            f"`{row['react_source']}` | `{row['python_source']}` |"
        )
    return "\n".join(lines) + "\n"

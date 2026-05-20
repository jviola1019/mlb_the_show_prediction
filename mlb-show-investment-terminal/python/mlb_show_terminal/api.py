"""FastAPI application for the React terminal."""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .artifacts import score_row
from .audit import audit_parity
from .backtesting import evaluate_strategy_backtest
from .completed_order_backtesting import (
    evaluate_completed_order_backtest,
    evaluate_historical_snapshot_backtest,
    fetch_completed_order_backtest,
    fetch_historical_snapshot_backtest,
)
from .historical import evaluate_backtest
from .market import validate_flip_formula
from .mlb_stats import MLBStatsError, recent_vs_season
from .ledger import persist_ledger_row, realized_trade_metrics
from .persistence import persistence_status
from .provenance import provenance_for_listing
from .scan import analyze_listing, enrich_scan_fields, scan_payload
from .scan_jobs import get_scan_job, start_scan_job
from .strategy_matrix import build_strategy_record
from .theshow import TheShowError, discover_top_listings, get_listing, search_card
from .upgrade import score_upgrade


STARTED_AT = time.time()


def _surface_verdict(record: dict[str, Any]) -> None:
    """Copy the forecast.verdict block to the record root for client convenience.

    The React UI reads ``record.verdict.status`` to decide whether to render
    BlockedPlaceholder / ObservationalOverlay / full 3D viz. Keeping the verdict
    only nested forced every consumer to walk through the forecast block.
    """
    forecast = record.get("forecast") if isinstance(record.get("forecast"), dict) else {}
    verdict = forecast.get("verdict") if isinstance(forecast.get("verdict"), dict) else None
    if isinstance(verdict, dict) and verdict.get("status"):
        record["verdict"] = verdict
        record["verdict_status"] = verdict.get("status")
        record["gates_failed_csv"] = verdict.get("failed_csv", record.get("gates_failed_csv", ""))


class AnalyzeRequest(BaseModel):
    listing: dict[str, Any] | None = None
    row: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None


class ScanRequest(BaseModel):
    uuids: list[str] | str | None = None
    uuid_text: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    stats_by_uuid: dict[str, dict[str, Any]] = Field(default_factory=dict)
    mode: str = "paste_uuids"
    rarity: str | None = None
    top_n: int | None = None
    session_uuids: list[str] = Field(default_factory=list)
    rate_delay: float | None = None
    enrich_mlb_stats: bool = True
    year: int = 26


class ValidateCardRequest(BaseModel):
    sell_price: Any = None
    buy_price: Any = None
    listing: dict[str, Any] | None = None
    row: dict[str, Any] | None = None


class UpgradeRequest(BaseModel):
    recent: dict[str, Any] = Field(default_factory=dict)
    season: dict[str, Any] = Field(default_factory=dict)
    role: str = "hitter"
    current_ovr: Any = None
    rarity: Any = None
    new_rank: Any = None


class BacktestRequest(BaseModel):
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[dict[str, Any]] = Field(default_factory=list)
    n_bins: int = 5
    id_col: str = "uuid"
    prob_col: str = "p_cross_next_threshold"
    outcome_col: str = "crossed_next_threshold"
    decision_threshold: float = 0.50
    min_n: int = 30
    min_events: int = 1


class StrategyBacktestRequest(BaseModel):
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    min_snapshots: int = 30
    tax_rate: float = 0.10


class CompletedOrderBacktestRequest(BaseModel):
    listings: list[dict[str, Any]] = Field(default_factory=list)
    uuids: list[str] | str | None = None
    uuid_text: str | None = None
    year: int = 26
    min_orders: int = 30
    lookback_orders: int = 20
    horizons_days: list[int] = Field(default_factory=lambda: [1, 3, 7])
    tax_rate: float = 0.10


class HistoricalSnapshotBacktestRequest(BaseModel):
    listings: list[dict[str, Any]] = Field(default_factory=list)
    uuids: list[str] | str | None = None
    uuid_text: str | None = None
    year: int = 26
    min_snapshots: int = 30
    lookback_snapshots: int = 9
    horizons_days: list[int] = Field(default_factory=lambda: [1, 3, 7])
    tax_rate: float = 0.10


class LedgerRequest(BaseModel):
    row: dict[str, Any]


class LedgerSummaryRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    tax_rate: float = 0.10


def create_app(static_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="MLB Show Investment Terminal API", version="1.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": app.version,
            "quant_owner": "python",
            "frontend": "react",
            "server_time": _utc_now(),
            "persistence": persistence_status(),
        }

    @app.get("/api/session/summary")
    def session_summary() -> dict[str, Any]:
        return {
            "status": "stateless",
            "server_time": _utc_now(),
            "started_at": _utc_from_ts(STARTED_AT),
            "runtime_seconds": round(time.time() - STARTED_AT, 3),
            "runtime_writes": persistence_status(),
            "historical_data": "real snapshots only; degraded until Supabase or committed artifacts exist",
        }

    @app.get("/api/persistence/status")
    def read_persistence_status() -> dict[str, Any]:
        return persistence_status()

    @app.get("/api/roster/updates")
    def roster_updates() -> dict[str, Any]:
        return {
            "status": "unavailable",
            "server_time": _utc_now(),
            "source": "versioned roster-update artifacts",
            "updates": [],
            "reason": "No roster update artifact has been committed for this React parity build.",
        }

    @app.get("/api/audit/parity")
    def parity_audit() -> dict[str, Any]:
        return audit_parity(Path(__file__).resolve().parents[2])

    @app.get("/api/search")
    def search(name: str, year: int = 26) -> dict[str, Any]:
        try:
            return search_card(name, year=year)
        except TheShowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/live/top-listings")
    def live_top_listings(rarity: str = "Gold", top_n: int = 25, year: int = 26) -> dict[str, Any]:
        try:
            return discover_top_listings(rarity=rarity, top_n=top_n, year=year)
        except TheShowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/mlb/player-stats")
    def mlb_player_stats(name: str, role: str = "auto", days: int = 14) -> dict[str, Any]:
        try:
            resolved_role = None if role == "auto" else role
            return recent_vs_season(name, role=resolved_role, days=days)
        except MLBStatsError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/listing/{uuid}")
    def listing(uuid: str, year: int = 26) -> dict[str, Any]:
        try:
            return get_listing(uuid, year=year)
        except TheShowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/card/analyze")
    def card_analyze(req: AnalyzeRequest, request: Request) -> dict[str, Any]:
        if req.listing is not None:
            payload = analyze_listing(req.listing, stats=req.stats, collect=_persistence_write_authorized(request))
            _surface_verdict(payload)
            return payload
        if req.row is not None:
            scored = score_row(req.row)
            scored["card"] = req.row
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
                "tier": "UNRATED",
                "verdict": {
                    "status": "OBSERVATIONAL ONLY",
                    "headline": "OBSERVATIONAL ONLY - no listing payload, governance skipped",
                    "failed": ["history_sufficient", "data_fresh", "cv_available"],
                    "failed_csv": "history_sufficient,data_fresh,cv_available",
                    "reasons": ["row-only entry; listing required for forecast governance"],
                    "badge_tone": "warn",
                },
            }
            scored["strategy"] = build_strategy_record(scored)
            scored["provenance"] = provenance_for_listing(
                None,
                sample_size=0,
                validation_tier="UNVALIDATED",
                rule_version=scored["strategy"].get("rule_version"),
            )
            return enrich_scan_fields(scored)
        raise HTTPException(status_code=400, detail="listing or row is required")

    @app.post("/api/card/validate")
    def card_validate(req: ValidateCardRequest) -> dict[str, Any]:
        sell_price = req.sell_price
        buy_price = req.buy_price
        if req.listing is not None:
            sell_price = req.listing.get("best_sell_price", sell_price)
            buy_price = req.listing.get("best_buy_price", buy_price)
        if req.row is not None:
            sell_price = req.row.get("raw_ask", req.row.get("ask", sell_price))
            buy_price = req.row.get("raw_bid", req.row.get("bid", buy_price))
        return {
            "status": "ok",
            "diagnostic": "manual flip formula validation",
            "validation": validate_flip_formula(sell_price, buy_price),
        }

    @app.post("/api/scan")
    def scan(req: ScanRequest, request: Request) -> dict[str, Any]:
        request_payload = req.model_dump()
        request_payload["_persistence_authorized"] = _persistence_write_authorized(request)
        payload = scan_payload(request_payload)
        for rec in payload.get("records") or []:
            _surface_verdict(rec)
        return payload

    @app.post("/api/scan/jobs")
    def create_scan_job(req: ScanRequest, request: Request) -> dict[str, Any]:
        payload = req.model_dump()
        if payload.get("rate_delay") is None:
            payload["rate_delay"] = 1.5
        payload["_persistence_authorized"] = _persistence_write_authorized(request)
        return start_scan_job(payload)

    @app.get("/api/scan/jobs/{job_id}")
    def read_scan_job(job_id: str) -> dict[str, Any]:
        job = get_scan_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="scan job not found")
        return job

    @app.post("/api/upgrade/score")
    def upgrade(req: UpgradeRequest) -> dict[str, Any]:
        return score_upgrade(
            recent=req.recent,
            season=req.season,
            role=req.role,
            current_ovr=req.current_ovr,
            rarity=req.rarity,
            new_rank=req.new_rank,
        ).to_dict()

    @app.post("/api/backtest/upgrades")
    def backtest(req: BacktestRequest) -> dict[str, Any]:
        return evaluate_backtest(
            req.predictions,
            req.labels,
            id_col=req.id_col,
            prob_col=req.prob_col,
            outcome_col=req.outcome_col,
            decision_threshold=req.decision_threshold,
            n_bins=req.n_bins,
            min_n=req.min_n,
            min_events=req.min_events,
        )

    @app.post("/api/backtest/strategy")
    def strategy_backtest(req: StrategyBacktestRequest) -> dict[str, Any]:
        return evaluate_strategy_backtest(
            req.snapshots,
            min_snapshots=req.min_snapshots,
            tax_rate=req.tax_rate,
        )

    @app.post("/api/backtest/completed-orders")
    def completed_order_backtest(req: CompletedOrderBacktestRequest) -> dict[str, Any]:
        uuid_values = _uuid_values(req.uuids, req.uuid_text)
        try:
            if uuid_values:
                return fetch_completed_order_backtest(
                    uuid_values,
                    year=req.year,
                    min_orders=req.min_orders,
                    lookback_orders=req.lookback_orders,
                    horizons_days=req.horizons_days,
                    tax_rate=req.tax_rate,
                )
            return evaluate_completed_order_backtest(
                req.listings,
                min_orders=req.min_orders,
                lookback_orders=req.lookback_orders,
                horizons_days=req.horizons_days,
                tax_rate=req.tax_rate,
            )
        except TheShowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/backtest/historical-snapshots")
    def historical_snapshot_backtest(req: HistoricalSnapshotBacktestRequest) -> dict[str, Any]:
        uuid_values = _uuid_values(req.uuids, req.uuid_text)
        try:
            if uuid_values:
                return fetch_historical_snapshot_backtest(
                    uuid_values,
                    year=req.year,
                    min_snapshots=req.min_snapshots,
                    lookback_snapshots=req.lookback_snapshots,
                    horizons_days=req.horizons_days,
                    tax_rate=req.tax_rate,
                )
            return evaluate_historical_snapshot_backtest(
                req.listings,
                min_snapshots=req.min_snapshots,
                lookback_snapshots=req.lookback_snapshots,
                horizons_days=req.horizons_days,
                tax_rate=req.tax_rate,
            )
        except TheShowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/ledger/log")
    def ledger_log(req: LedgerRequest, request: Request) -> dict[str, Any]:
        _require_write_auth(request)
        return persist_ledger_row(req.row)

    @app.post("/api/ledger/summary")
    def ledger_summary(req: LedgerSummaryRequest) -> dict[str, Any]:
        return realized_trade_metrics(req.rows, tax_rate=req.tax_rate)

    root = Path(static_dir or os.environ.get("MLB_SHOW_STATIC_DIR", "")).resolve() if (static_dir or os.environ.get("MLB_SHOW_STATIC_DIR")) else None
    if root and root.exists():
        assets = root / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            target = root / path
            if path and target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(root / "index.html")

    return app

def _utc_now() -> str:
    return _utc_from_ts(time.time())


def _utc_from_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _uuid_values(uuids: list[str] | str | None, uuid_text: str | None = None) -> list[str]:
    raw: list[str] = []
    if isinstance(uuids, list):
        raw.extend(str(x) for x in uuids)
    elif isinstance(uuids, str):
        raw.extend(part.strip() for part in uuids.replace(",", "\n").splitlines())
    if uuid_text:
        raw.extend(part.strip() for part in uuid_text.replace(",", "\n").splitlines())
    return list(dict.fromkeys(x.lower() for x in raw if x))


def _require_write_auth(request: Request) -> None:
    status = persistence_status()
    if status.get("status") != "configured":
        return
    expected = os.environ.get("TERMINAL_WRITE_TOKEN") or os.environ.get("MLB_SHOW_WRITE_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="server-side persistence is configured but TERMINAL_WRITE_TOKEN is not set",
        )
    supplied = request.headers.get("x-terminal-write-token") or request.headers.get("x-api-key")
    if not supplied or not secrets.compare_digest(str(supplied), str(expected)):
        raise HTTPException(status_code=403, detail="write token required")


def _persistence_write_authorized(request: Request) -> bool:
    status = persistence_status()
    if status.get("status") != "configured":
        return False
    expected = os.environ.get("TERMINAL_WRITE_TOKEN") or os.environ.get("MLB_SHOW_WRITE_TOKEN")
    if not expected:
        return False
    supplied = request.headers.get("x-terminal-write-token") or request.headers.get("x-api-key")
    return bool(supplied and secrets.compare_digest(str(supplied), str(expected)))


def _cors_origins() -> list[str]:
    raw = os.environ.get("TERMINAL_CORS_ORIGINS") or os.environ.get("MLB_SHOW_CORS_ORIGINS")
    if raw:
        origins = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
        if origins:
            return origins
    return [
        "http://127.0.0.1:7860",
        "http://localhost:7860",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://jviola1019-mlb-show-investment-terminal.hf.space",
    ]


app = create_app()

"""FastAPI application for the React terminal."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .artifacts import score_row
from .audit import audit_parity
from .historical import evaluate_backtest
from .market import validate_flip_formula
from .mlb_stats import MLBStatsError, recent_vs_season
from .scan import analyze_listing, scan_payload
from .scan_jobs import get_scan_job, start_scan_job
from .theshow import TheShowError, discover_top_listings, get_listing, search_card
from .upgrade import score_upgrade


STARTED_AT = time.time()


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


def create_app(static_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="MLB Show Investment Terminal API", version="1.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
        }

    @app.get("/api/session/summary")
    def session_summary() -> dict[str, Any]:
        return {
            "status": "stateless",
            "server_time": _utc_now(),
            "started_at": _utc_from_ts(STARTED_AT),
            "runtime_seconds": round(time.time() - STARTED_AT, 3),
            "runtime_writes": "prohibited",
            "historical_data": "versioned artifacts only",
        }

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
    def card_analyze(req: AnalyzeRequest) -> dict[str, Any]:
        if req.listing is not None:
            return analyze_listing(req.listing, stats=req.stats)
        if req.row is not None:
            scored = score_row(req.row)
            scored["card"] = req.row
            scored["forecast"] = {
                "status": "unavailable",
                "diagnostic_only": True,
                "reason": "listing payload required for price-history diagnostics",
            }
            return scored
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
    def scan(req: ScanRequest) -> dict[str, Any]:
        return scan_payload(req.model_dump())

    @app.post("/api/scan/jobs")
    def create_scan_job(req: ScanRequest) -> dict[str, Any]:
        payload = req.model_dump()
        if payload.get("rate_delay") is None:
            payload["rate_delay"] = 1.5
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
        return evaluate_backtest(req.predictions, req.labels, n_bins=req.n_bins)

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


app = create_app()


def _utc_now() -> str:
    return _utc_from_ts(time.time())


def _utc_from_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

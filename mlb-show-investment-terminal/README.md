# MLB · INVESTMENT TERMINAL

Quantitative analysis tool for the MLB The Show in-game card market. Live data only — no synthetic prices ever shipped to the user. Every recommendation passes through a 7-gate governance system before any action verb (BUY / SELL / HOLD) is published.

## Architecture

- **Backend** — FastAPI in `python/mlb_show_terminal/`. Sole quant owner: forecasting, walk-forward CV, isotonic calibration, EV, validation gates.
- **Frontend** — React 19 + TypeScript + Vite in `frontend/`. Six tabs (CARD, OVR PRED, MARKET SCAN, VALIDATE, METHOD, OVERALL) with a lazy-loaded 3D viz layer (`frontend/src/viz/`).
- **Deploy** — Single Docker image built by `Dockerfile.react` and used by Render (`render.yaml`), Hugging Face Docker Spaces (`huggingface/Dockerfile`), and local `docker-compose.react.yml`. Listens on port 7860.

Earlier the project had an R/Shiny implementation; it was sunset on 2026-05-10 once the React+Python build reached parity. The R sources, `renv` lock, and ShinyApps deploy artifacts have been removed.

## The 7-gate governance system

Every CARD-tab recommendation passes through seven gates in `python/mlb_show_terminal/governance.py`:

| # | Gate | Threshold | Severity |
|---|------|-----------|----------|
| 1 | `schema_valid` | UUID + ask/bid > 0 + ≥ 8 completed orders | hard |
| 2 | `history_sufficient` | ≥ max(50, 6 × horizon) price points | hard |
| 3 | `data_fresh` | most recent tick ≤ 48 h | hard |
| 4 | `cv_available` | walk-forward CV produced ≥ 30 trades | hard |
| 5 | `cv_skill_not_negative_sig` | IC upper CI ≥ 0 | soft |
| 6 | `ci_width_acceptable` | Brier CI width ≤ 0.20 AND IC CI width ≤ 0.50 | soft |
| 7 | `calibration_present` | reliability binning produced ≥ 5 usable bins | soft |

Verdict tiers:

- **INVESTABLE** — all 7 pass. Full recommendation, EV table, 3D forecast surface.
- **OBSERVATIONAL ONLY** — hard pass + soft fail. Direction shown (▲/▼), action verb suppressed, EV cells blanked, no Kelly sizing; excluded from TOP BUY / TOP SELL.
- **NOT INVESTABLE** — any hard fail. ABSTAIN verdict, forecast cone replaced with `<BlockedPlaceholder>`, EV table blanked entirely.

Visuals (recharts cone, 3D viz, EV grid, Kelly stat) are wrapped in `frontend/src/verdictGuard.tsx` so a polished UI cannot overstate confidence under failed validation.

## 3D visualization layer

- `frontend/src/viz/ForecastSurface3D.tsx` — react-three-fiber translucent ribbon (p5..p50..p95) over horizon × price for CARD.
- `frontend/src/viz/ScanDepthHeatmap3D.tsx` — echarts-gl bar field (OVR × liquidity × ROI, color = tier) for MARKET SCAN.
- `frontend/src/viz/TierOvrEvScatter3D.tsx` — echarts-gl scatter (OVR × tier × forecast EV, color = verdict) for OVERALL.
- `frontend/src/viz/ReliabilityRibbon3D.tsx` — r3f calibration ribbon for VALIDATE.

Each is lazy-loaded so a fresh page paint doesn't ship WebGL bundles to users who don't navigate to those tabs.

## Run locally

```powershell
python -m pip install -e ".[test]"
cd frontend
npm install
npm run build
cd ..
$env:MLB_SHOW_STATIC_DIR = "$PWD\frontend\dist"
uvicorn mlb_show_terminal.api:app --host 0.0.0.0 --port 7860
```

Open `http://127.0.0.1:7860`. On a phone on the same Wi-Fi, use `http://<desktop-lan-ip>:7860`.

Frontend dev (with hot reload, proxies `/api` to a separately-running backend on 7860):

```powershell
cd frontend
npm run dev   # http://localhost:5173
```

## Tests

```powershell
# Python (51 tests including 15 governance + 4 scan-job LRU)
python -m pytest python/tests/ -v

# Frontend (Vitest)
cd frontend
npx tsc -b --noEmit
npm test -- --run

# Frontend e2e smoke (Playwright)
npm run smoke
```

## Deploy

```powershell
# Render: uses Dockerfile.react via render.yaml; health check at /api/health
# Hugging Face Space:
python -m pip install -e ".[deploy]"
$env:HF_TOKEN = "<token with write access>"
python scripts/publish_hf_space.py --repo-id jviola1019/mlb-show-investment-terminal
```

`scripts/publish_hf_space.py` uploads a clean Space bundle (React source, Python package, root `Dockerfile.react`, Space `README.md`) and excludes node_modules, build artifacts, caches, and test output.

## License

See `LICENSE`.

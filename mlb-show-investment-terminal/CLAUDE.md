# Project conventions — MLB Investment Terminal

Single-stack Python + React app. **Do not propose edits to R/Shiny code** — that stack was sunset 2026-05-10 and the source is gone.

## Architecture

- **Backend:** FastAPI in `python/mlb_show_terminal/` is the **sole quant owner**. All forecasting, governance, partitioning, and EV math lives here.
- **Frontend:** React 19 + TypeScript strict + Vite in `frontend/`. The only UI; tabs CARD, OVR, SCAN, VALIDATE, METHOD, OVERALL.
- **Deploy:** Docker single-image (`Dockerfile.react`) used by Render (`render.yaml`), Hugging Face Docker Spaces (`huggingface/Dockerfile`), and local compose (`docker-compose.react.yml`). All on port 7860.

## The 7-gate governance system (load-bearing)

`python/mlb_show_terminal/governance.py` is the **single source of truth** for verdicts. Seven gates:

1. `schema_valid` — listing has UUID, ask/bid > 0, ≥ 8 completed_orders **(hard)**
2. `history_sufficient` — ≥ max(50, 6 × horizon) price points **(hard)**
3. `data_fresh` — most recent tick ≤ 48 h **(hard)**
4. `cv_available` — walk-forward CV produced ≥ 30 trades **(hard)**
5. `cv_skill_not_negative_sig` — IC upper CI ≥ 0 **(soft)**
6. `ci_width_acceptable` — Brier CI ≤ 0.20 AND IC CI ≤ 0.50 **(soft)**
7. `calibration_present` — reliability binning produced ≥ 5 usable bins **(soft)**

Verdicts:

- **INVESTABLE** — all 7 pass; full BUY/SELL/HOLD and 3D viz shown.
- **OBSERVATIONAL ONLY** — hard pass, soft fail; direction only, no action verb, EV/Kelly cells blanked, excluded from TOP BUY / TOP SELL.
- **NOT INVESTABLE** — any hard fail; ABSTAIN, blocked placeholder, no forecast cone rendered.

**Never** compute BUY/SELL labels in code paths that bypass `gating_verdict()`. Visuals must accept the verdict status as a prop and degrade via `frontend/src/verdictGuard.tsx`.

## 3D visualization layer

Lazy-loaded under `frontend/src/viz/`:

- `ForecastSurface3D.tsx` — r3f cone surface in CARD tab
- `ScanDepthHeatmap3D.tsx` — echarts-gl bar field in SCAN tab
- `TierOvrEvScatter3D.tsx` — echarts-gl scatter in OVERALL tab
- `ReliabilityRibbon3D.tsx` — r3f reliability ribbon in VALIDATE tab

Each accepts the record/verdict and degrades to recharts or a `<BlockedPlaceholder>` under failed gates.

## Test commands

```powershell
# backend
python -m pip install -e ".[test]"
python -m pytest python/tests/ -v

# frontend
cd frontend
npm install
npx tsc -b --noEmit
npm test
npm run build
```

## Conventions

- No runtime writes (API returns `runtime_writes: "prohibited"`); artifacts only.
- No synthetic price data. Live API responses only.
- LLM cross-check (if used) is commentary-only — never influences statistical state.
- Bid/ask after-tax math uses `tax_rate` parameter (default 0.10 → 90% net after market tax). Hard-coded `0.90` factors are a regression — flag in review.
- React tabs receive `ctx: TerminalContext` for shared state (loaded UUIDs, last scan, current record); never store data outside this context.

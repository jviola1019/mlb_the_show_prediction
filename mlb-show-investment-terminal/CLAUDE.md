# Project Conventions - MLB Show Investment Terminal

Single-stack Python + React app. Do not propose edits to R/Shiny code. That stack was sunset on 2026-05-10.

## Architecture

- **Backend:** FastAPI in `python/mlb_show_terminal/` owns quant logic, strategy ontology, forecast diagnostics, execution math, backtests, persistence, and provenance.
- **Frontend:** React 19 + TypeScript strict + Vite in `frontend/`. The terminal has 10 tabs: Command Center, Market Scanner, Target / Trade Ticket, Strategy Matrix, Forecast Lab, Backtesting & Validation, Execution Ledger, Risk & Inventory, Data Provenance & Audit, and README / Operations.
- **Deploy:** Docker single-image on port `7860` for Hugging Face Spaces, Render, and local runs.

## Strategy Semantics

`strategy.*` is the source of truth for user-facing trade meaning.

- `strategy.flip`: spread-capture math after tax, friction, exit probability, expected holding time, and liquidation risk.
- `strategy.directional`: 1d/3d/7d directional EV, quantiles, probability, model confidence, and hold horizon.
- `strategy.inventory`: liquidity tier, dead-inventory risk, exit time, and position cap.
- `strategy.composite`: final action from the deterministic matrix.

`INVESTABLE` is directional-only. It is not a final action and must never appear for bearish or negative-EV cards. A positive spread with a bearish forecast becomes `INSTANT FLIP ONLY`, `SPREAD CAPTURE ONLY`, or manual review depending on liquidity and freshness.

## Validation Semantics

Do not collapse sample depth and profitability proof into one tier.

- `data_coverage_tier`: real-history depth only.
- `performance_validation_tier`: after-tax strategy performance, baseline comparison, and calibration evidence.
- `validation_tier`: legacy compatibility alias for `performance_validation_tier`.

`SILVER` coverage can still be a losing strategy. Do not promote a strategy to `GOLD` or `PLATINUM` without real after-cost baseline outperformance and calibration evidence.

The older 7-gate forecast governance still exists for directional diagnostics, but final action semantics now come from the strategy ontology and composite matrix.

## Persistence

Runtime writes are allowed only through server-side persistence with explicit safeguards:

- Browser code never receives Supabase service credentials.
- `SUPABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_KEY` enables Supabase REST writes.
- `SUPABASE_DB_URL` enables direct Postgres only when `psycopg` is installed.
- HTTP write endpoints require `TERMINAL_WRITE_TOKEN` or `MLB_SHOW_WRITE_TOKEN` and the `X-Terminal-Write-Token` header.
- Public scan/analyze routes skip collection unless a trusted write token is present.
- If persistence is missing, the app starts in read-only degraded mode.

Default CORS is an allowlist for localhost dev origins and the Hugging Face Space URL. Override with `TERMINAL_CORS_ORIGINS` or `MLB_SHOW_CORS_ORIGINS`; do not use `*` in production.

## Data Policy

- No synthetic production market data.
- No fake historical backfill.
- Test fixtures are allowed only for automated tests and must not be presented as production history.
- Retained The Show `price_history` rows can validate limited bid/ask price paths.
- Retained `completed_orders` rows can validate directional sale-print behavior only, not spread-fill execution.
- Realized execution quality requires user ledger rows or account/exported fills.

## Test Commands

```powershell
python -m pip install -e ".[test]"
python -m pytest python/tests/ -v

cd frontend
npm ci
npx tsc -b --noEmit
npm test -- --run
npm run build
```

For local smoke:

```powershell
$env:MLB_SHOW_STATIC_DIR = "$PWD\frontend\dist"
python -m uvicorn mlb_show_terminal.api:app --host 127.0.0.1 --port 7860
cd frontend
$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:7860"
npm run smoke
```

## Conventions

- Preserve existing dirty-user changes. Do not revert files unless explicitly asked.
- Keep legacy flat API fields during migration, but make new UI and docs prefer `strategy.*`.
- Bid/ask after-tax math uses the configured `tax_rate` parameter, default `0.10`.
- Hold recommendations must include a horizon such as `1d`, `3d`, `7d`, or manual review.
- Do not relax thresholds to force profitable output.

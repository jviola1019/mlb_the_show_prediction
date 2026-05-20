# FINAL AUDIT

Date: 2026-05-20

## Executive Summary

Final verdict: **LIMITED PASS**.

The original semantic contradiction is fixed. Spread flip, directional forecast, inventory quality, and final action are separate first-class outputs under `strategy.*`. `INVESTABLE` is directional-only and is not a final action. A card with positive spread capture but bearish/negative directional EV maps to a flip-only or avoid/manual-review action, not an investment label.

The product is **limited-use/data-collection only**, not production-profitable. Current tests pass and retained real history is usable, but the latest bounded retained-history run does not beat comparable naive baselines after tax and has no calibration audit. Supabase persistence is disabled on the live Hugging Face Space, so forward snapshot and ledger accumulation are not active in production until Space secrets are configured.

## Files Changed

Primary backend additions and changes:

- `python/mlb_show_terminal/strategy_ontology.py`
- `python/mlb_show_terminal/strategy_matrix.py`
- `python/mlb_show_terminal/inventory.py`
- `python/mlb_show_terminal/provenance.py`
- `python/mlb_show_terminal/validation_tiers.py`
- `python/mlb_show_terminal/backtesting.py`
- `python/mlb_show_terminal/completed_order_backtesting.py`
- `python/mlb_show_terminal/retained_history.py`
- `python/mlb_show_terminal/persistence.py`
- `python/mlb_show_terminal/collector.py`
- `python/mlb_show_terminal/ledger.py`
- `python/mlb_show_terminal/api.py`
- `python/mlb_show_terminal/scan.py`
- `python/mlb_show_terminal/cli.py`
- `supabase/schema.sql`

Primary frontend additions and changes:

- `frontend/src/strategyComponents.tsx`
- `frontend/src/tabs/TerminalTabs.tsx`
- `frontend/src/tabs/CardTab.tsx`
- `frontend/src/tabs/ScanTab.tsx`
- `frontend/src/tabs/ValidateTab.tsx`
- `frontend/src/tabs/OverallTab.tsx`
- `frontend/src/tabs/MethodTab.tsx`
- `frontend/src/tabs/OvrTab.tsx`
- `frontend/src/components.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/TerminalBackdrop.tsx`
- `frontend/e2e/smoke.spec.ts`
- `frontend/scripts/check-bundle-budget.mjs`
- `frontend/package.json`
- `frontend/package-lock.json`

Primary tests and docs:

- `python/tests/test_strategy_matrix.py`
- `python/tests/test_strategy_backtesting.py`
- `python/tests/test_completed_order_backtesting.py`
- `python/tests/test_retained_history.py`
- `python/tests/test_persistence_ledger.py`
- `python/tests/test_api.py`
- `README.md`
- `CLAUDE.md`
- `docs/parity/python-react-parity.md`
- `docs/history/*.md` archival notes
- `huggingface/README.md`
- `FINAL_AUDIT.md`

There were pre-existing dirty files from earlier sprint work. They were not reverted.

## Architecture Changes

- Added typed strategy ontology for flip, directional, inventory, composite, validation, and hold horizon semantics.
- Added deterministic composite matrix matching the required prompt rows.
- Preserved legacy flat API fields during migration while making `strategy.*` the truth source.
- Split validation semantics into `data_coverage_tier` and `performance_validation_tier`. Legacy `validation_tier` now mirrors performance validation.
- Added provenance payloads with source URL, pull timestamp, freshness, sample size, data hash, model version, rule version, and split validation tiers.
- Added Supabase schema and server-side persistence adapter with table/column whitelisting.
- Public scan/analyze routes now skip persistence collection unless a trusted write token is present.
- Added CORS allowlist support through `TERMINAL_CORS_ORIGINS` or `MLB_SHOW_CORS_ORIGINS`; default is not wildcard.
- Added read-only degraded health/status behavior when Supabase credentials or `psycopg` are absent.
- Added execution ledger helpers and realized-edge metrics.
- Added real-history backtests for retained bid/ask `price_history`, retained `completed_orders`, collected market snapshots, roster-update labels, and user ledger imports.

## Current Issue Inventory

| Sev | Issue | Location / Evidence | Status |
|---|---|---|---|
| P0 | Not production-profitable. Latest retained-history strategy has `SILVER` coverage but only `BRONZE` performance and does not beat comparable baselines. | `artifacts/history/retained-market-discovery-2026-05-20.json` | Open |
| P0 | Live HF persistence is disabled, so production snapshot/ledger accumulation is not active. | live `/api/health`, `/api/persistence/status` | Open until Supabase secrets are configured |
| P1 | Upgrade probabilities remain scenario heuristics, not calibrated probabilities. | `python/mlb_show_terminal/upgrade.py` | Open |
| P1 | Full spread-fill execution cannot be proven from completed-order sale prints alone. | `completed_order_backtesting.py`, retained-history source limitations | Open |
| P1 | Historical bid/ask backtest validates retained price paths, but not queue position, order-book depth, or failed-exit mechanics. | `completed_order_backtesting.py`, `backtesting.py` | Open |
| P1 | Action-specific execution model is improved but still proxy-based until real depth and ledger fills accumulate. | `backtesting.py` | Open |
| P1 | Hard thresholds still need empirical calibration, not relaxation. | `market.py`, `strategy_matrix.py` | Open |
| P1 | Production release is from a dirty workspace rather than a clean tagged commit. | `git status` | Open |
| P2 | Vite still warns about chart/3D chunks larger than 650 kB. Budget check passes but mobile performance should be monitored. | frontend build output | Open |
| P2 | Automated accessibility now checks serious/critical axe findings on Command Center, but not full WCAG/Lighthouse coverage across every data-dense state. | `frontend/e2e/smoke.spec.ts` | Open |
| P2 | Dense real-data chart clipping is smoke-tested, but not exhaustively across every tab and all live market extremes. | Playwright smoke scope | Open |
| P2 | Empty states exist, but scanner elimination counts by every gate are not yet complete. | scanner UI | Open |
| P2 | Third-party history sources can inform concepts, but ingestion needs API permission/terms review before production use. | ShowZone/7th Inning/public repos review | Open |
| P3 | Older docs are archival and contain pre-ontology terms; they now have archival notes but should not guide implementation. | `docs/history/*.md` | Mitigated |
| P3 | HF CLI binary is not installed locally; deployment used `huggingface_hub` through the repo script. | local environment | Mitigated |

## Data-Source Audit

No synthetic production data was added. Automated tests use fixtures only.

Official The Show listing payloads expose retained `price_history` bid/ask rows and `completed_orders` sale prints. The implemented historical snapshot backtest uses real `price_history` rows when available. The completed-order backtest uses real sale prints for directional validation only and does not infer missing bid/ask depth.

Latest bounded retained-history run:

- Command: `python -m mlb_show_terminal.cli collect-retained-history --rarities Diamond Gold Silver --per-rarity 5 --output artifacts\history\retained-market-discovery-2026-05-20.json --rate-delay 0.1`
- Cards fetched: 15 real listings.
- Retained historical bid/ask rows: 469.
- Retained completed-sale prints: 2,961.
- Bid/ask date range: 2026-03-31 through 2026-05-19.
- Completed-sale date range: 2026-05-18T22:06:28Z through 2026-05-20T05:47:01Z.
- Errors: none.

Realized ledger outcomes are not public market data. They must come from manual trade logging, Supabase `execution_ledger`, or user-authored/account-exported fills.

## Model Audit

- `FLIP PASS`, `FLIP MARGINAL`, `NO FLIP EDGE`, and `DO NOT FLIP` are separate from directional labels.
- Directional labels are `BULLISH`, `NEUTRAL`, `BEARISH`, or `INSUFFICIENT DATA`.
- Inventory labels are `HIGH LIQUIDITY`, `MEDIUM LIQUIDITY`, `THIN`, or `DEAD INVENTORY`.
- Composite final actions include `INSTANT FLIP ONLY`, `SPREAD CAPTURE ONLY`, `FLIP OR SHORT HOLD`, `SPECULATIVE HOLD`, `WATCHLIST / NO MODEL TRADE`, `AVOID`, and `AVOID / MANUAL REVIEW`.
- Directional `INVESTABLE` requires positive after-cost EV, acceptable probability support, and validation gates. Negative EV or `P(profit)=0` blocks it.
- Positive directional recommendations include a hold horizon such as `1d`, `3d`, `7d`, or manual review.

## Backtest Audit

Implemented frameworks:

- Collected snapshot strategy backtest: real timestamped market snapshots only.
- Retained The Show `price_history` backtest: deterministic rolling-origin bid/ask path validation.
- Retained The Show `completed_orders` backtest: deterministic rolling-origin directional sale-print validation.
- Upgrade backtest: pre/post roster artifacts only.
- Ledger import summary: user-authored realized fills only.

Latest retained `price_history` backtest:

- Status: `available`.
- Data coverage tier: `SILVER`.
- Performance validation tier: `BRONZE`.
- Validation verdict: `LIMITED`.
- Evaluated opportunities: 1,046.
- Trades taken: 937.
- Baseline comparison: model total stubs `111,272.3`; naive spread-only `240,702.5`; random trade `155,073.8`; naive momentum `69,944.4`; no-trade `0.0`.
- Promotion blockers: `DOES_NOT_BEAT_NAIVE_BASELINES`, `CALIBRATION_AUDIT_UNAVAILABLE`.
- 1d: total stubs `74,986.3`, hit rate `86.18%`, profit factor `2.19`, failed-exit rate `13.82%`.
- 3d: total stubs `40,078.5`, hit rate `83.02%`, profit factor `1.40`, failed-exit rate `16.98%`.
- 7d: total stubs `-3,792.5`, hit rate `83.87%`, profit factor `0.96`, failed-exit rate `16.13%`.

Latest completed-order backtest:

- Status: `unavailable`.
- Data coverage tier: `UNVALIDATED`.
- Performance validation tier: `UNVALIDATED`.
- Reason: no 1d/3d/7d horizon labels in the retained completed-sale window.

This is evidence that the historical path is real and functioning. It is not evidence that the strategy is production-profitable.

## Statistical Validation Audit

Implemented/tested:

- Deterministic rolling-origin splits.
- No synthetic history fallback.
- No-lookahead feature construction by prior-window slicing.
- Strategy-specific execution assumptions in snapshot backtests.
- Baselines: no-trade, random, naive spread-only, naive momentum, naive no-change forecast, old gate logic.
- Metrics: ROI, stubs, hit rate, profit factor, drawdown, Sharpe-like ratio, Sortino-like ratio, failed-exit rate, turnover, stub velocity, opportunity cost.
- Split coverage/performance validation tiers.
- Matt Olson regression blocking final `INVESTABLE`.
- Negative EV blocking directional `INVESTABLE`.
- Dead inventory and stale/freshness downgrades.
- Persistence disabled mode, write token enforcement, and table/column whitelisting.
- Ledger realized profit/edge-decay math.

Not claimed:

- Calibrated upgrade probabilities.
- GOLD/PLATINUM performance validation.
- Production profitability.
- Queue/depth execution proof.

## UI/UX Audit

- Ten top-level tabs are implemented.
- Final action is visible in command center, scanner rows, strategy matrix, and trade ticket.
- Strategy summary separates flip, directional, inventory, coverage tier, and performance tier.
- Tables scroll horizontally with sticky first columns.
- Mobile uses a native section selector instead of an overflowing tab strip.
- Target card uses restrained CSS 3D treatment with reduced-motion support.
- Browser errors for persistence/ledger writes are surfaced as alerts.
- Data provenance and source timestamps are exposed.

## Mobile And Accessibility Audit

Verified:

- Playwright desktop and Pixel 7 projects passed.
- Canvas pixel probe confirms the terminal 3D backdrop renders nonblank.
- Command Center axe smoke has no serious or critical violations after excluding color-contrast from the automated pass.
- Scanner progress uses `role="progressbar"`.
- Liquidity dots use meter semantics and are not color-only.
- Scanner rows and tab controls are keyboard accessible.
- Manual controls have explicit labels.

Screenshot paths:

- `artifacts/screenshots/final-command-desktop-2026-05-20.png`
- `artifacts/screenshots/final-command-mobile-2026-05-20.png`

## Commands Run

```powershell
python -m pytest python/tests/ -q
cd frontend; npx tsc -b --noEmit
cd frontend; npm test -- --run
cd frontend; npm run build
cd frontend; npm run bundle:budget
$env:MLB_SHOW_STATIC_DIR=(Resolve-Path frontend/dist).Path; python -m uvicorn mlb_show_terminal.api:app --host 127.0.0.1 --port 7860
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7860/api/health
cd frontend; $env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:7860"; npm run smoke
python -m mlb_show_terminal.cli collect-retained-history --rarities Diamond Gold Silver --per-rarity 5 --output artifacts\history\retained-market-discovery-2026-05-20.json --rate-delay 0.1
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:7860/api/backtest/strategy -ContentType "application/json" -Body '{"snapshots":[],"min_snapshots":2}'
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7860/api/persistence/status
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:7860/api/ledger/log -ContentType "application/json" -Body '{"row":{"card_uuid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","buy_price":1000,"sell_price":1200,"timestamp":"2026-05-20T00:00:00Z","strategy_type":"flip"}}'
cd frontend; npx playwright screenshot --wait-for-timeout=2500 --viewport-size=1440,950 http://127.0.0.1:7860 ../artifacts/screenshots/final-command-desktop-2026-05-20.png
cd frontend; npx playwright screenshot --wait-for-timeout=2500 --device="Pixel 7" http://127.0.0.1:7860 ../artifacts/screenshots/final-command-mobile-2026-05-20.png
$env:HF_TOKEN="<redacted>"; python scripts\publish_hf_space.py --repo-id jviola1019/mlb-show-investment-terminal --timeout 900
Invoke-WebRequest -UseBasicParsing https://jviola1019-mlb-show-investment-terminal.hf.space/api/health
Invoke-WebRequest -UseBasicParsing -Method POST -Uri https://jviola1019-mlb-show-investment-terminal.hf.space/api/backtest/strategy -ContentType "application/json" -Body '{"snapshots":[],"min_snapshots":2}'
Invoke-WebRequest -UseBasicParsing https://jviola1019-mlb-show-investment-terminal.hf.space/api/persistence/status
```

## Test Results

- Python: `109 passed, 8 subtests passed`.
- TypeScript: passed.
- Vitest: `14 passed`.
- Production build: passed.
- Bundle budget: passed. Largest chunk `723,106` bytes; total JS assets `3,555,031` bytes.
- Vite warning remains for some chart/3D chunks over 650 kB.
- Playwright smoke: `14 passed`.
- Local `/api/health`: `status=ok`, `version=1.3.0`, persistence disabled/read-only degraded.
- Local empty strategy backtest: `UNVALIDATED`, `INSUFFICIENT_REAL_MARKET_SNAPSHOTS`, with split coverage/performance tiers.
- Local ledger write without persistence: disabled, no write.

## Deployment Notes

Hugging Face Space:

- URL: `https://jviola1019-mlb-show-investment-terminal.hf.space`
- Publish command completed after one transient Hub connection reset and retry.
- Remote source file check confirmed the uploaded `backtesting.py` includes split validation tiers.
- Live rebuild initially served the old backtest contract, then updated to the new split-tier response after rebuild.
- Live `/api/health` at `2026-05-20T05:51:11Z`: `status=ok`, `version=1.3.0`.
- Live persistence: `disabled`, `read-only degraded`, `credential_exposure=none`.
- Live empty strategy backtest: `UNVALIDATED`, `INSUFFICIENT_REAL_MARKET_SNAPSHOTS`, with `data_coverage_tier` and `performance_validation_tier`.

Production Supabase writes remain disabled until Space secrets are configured:

- `SUPABASE_URL` plus service key, or `SUPABASE_DB_URL` with `psycopg`.
- `TERMINAL_WRITE_TOKEN` or `MLB_SHOW_WRITE_TOKEN`.
- Optional CORS override through `TERMINAL_CORS_ORIGINS` or `MLB_SHOW_CORS_ORIGINS`.

## Final Verdict

**LIMITED PASS**.

The contradiction is fixed, tests pass, the UI is materially improved, the Space was reuploaded, and live endpoints are healthy. The system must remain limited-use/data-collection only until real forward snapshots, realized ledger outcomes, and calibration evidence support stronger after-tax baseline outperformance.

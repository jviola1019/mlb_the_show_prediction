# MLB Show Investment Terminal

Production-oriented trading terminal for the MLB The Show card market. The app separates spread flips, directional holds, inventory quality, and final action so a card can never be labeled as a directional investment merely because the bid/ask spread is positive.

## Strategy Ontology

- **Spread Flip Engine**: asks whether the current ask/bid can capture spread after 10% tax, slippage, liquidity, and exit risk.
- **Directional Forecast Engine**: asks whether the card has positive expected holding value over 1d, 3d, or 7d.
- **Inventory Quality Engine**: asks whether the position can be exited without getting trapped.
- **Composite Strategy Matrix**: combines the three verdicts into the action the user should take.

Final actions:

| Action | Meaning |
|---|---|
| `INSTANT FLIP ONLY` | Positive spread capture, but directional forecast is bearish. Buy only if you can immediately relist/exit. Do not hold. |
| `SPREAD CAPTURE ONLY` | Flip edge exists, but directional forecast is neutral. Exit as a spread trade. |
| `FLIP OR SHORT HOLD` | Flip edge and positive directional EV both clear gates. Hold only up to the stated horizon unless exit/risk gates trigger first. |
| `SPECULATIVE HOLD` | No spread edge, but directional EV is positive and inventory quality is acceptable. |
| `WATCHLIST / NO MODEL TRADE` | Real history, freshness, calibration, or validation is insufficient. Collect data; do not model-trade. |
| `AVOID` / `AVOID / MANUAL REVIEW` | Bearish/no-edge/dead-inventory conditions block entry. |
| `INVESTABLE` | Directional-only label. It can appear only inside `strategy.directional` when positive after-cost EV and validation gates pass. |

For the Matt Olson regression case with ask around `1,788`, bid around `1,521`, after-tax value around `1,609`, net spread around `88`, forecast EV around `-23.2%`, and `P(profit)=0%`, the correct final action is `INSTANT FLIP ONLY`, not `INVESTABLE`.

## Data Policy

No synthetic production data is allowed. The app uses live The Show market payloads, user-provided rows, Supabase snapshots, or committed historical artifacts. If historical snapshots or labels are missing, the UI reports `UNVALIDATED` and the strategy matrix returns `WATCHLIST / NO MODEL TRADE` instead of promoting confidence.

Forward collection is implemented through server-side Supabase writes. Active runtime endpoints can write market snapshots, model predictions, and execution-ledger rows when persistence is configured and the trusted write token is supplied. The schema also includes validation runs and audit events for offline jobs and later promotion workflows.

- `market_snapshots`
- `execution_ledger`
- `model_predictions`
- `validation_runs`
- `audit_events`

Schema is in `supabase/schema.sql`. Browser code never receives Supabase service credentials.

## Environment Variables

- `MLB_SHOW_STATIC_DIR`: path to `frontend/dist` when serving the built React app through FastAPI.
- `SUPABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_KEY`: enables server-side Supabase REST writes.
- `SUPABASE_DB_URL`: optional direct Postgres connection. Requires `psycopg` at runtime.
- `TERMINAL_WRITE_TOKEN` or `MLB_SHOW_WRITE_TOKEN`: required for HTTP write endpoints when persistence is configured. Send it as `X-Terminal-Write-Token` from trusted server-side tooling only; do not expose it in browser code.
- `TERMINAL_CORS_ORIGINS` or `MLB_SHOW_CORS_ORIGINS`: optional comma-separated browser origins for production. Defaults to localhost dev origins and the Hugging Face Space URL, not `*`.
- `HF_TOKEN`: Hugging Face write token for deployment.

If Supabase variables are absent, the app starts in read-only degraded mode and reports that status at `/api/persistence/status`.

## Install And Run Locally

```powershell
python -m pip install -e ".[test]"
cd frontend
npm ci
npm run build
cd ..
$env:MLB_SHOW_STATIC_DIR = "$PWD\frontend\dist"
python -m uvicorn mlb_show_terminal.api:app --host 127.0.0.1 --port 7860
```

Open `http://127.0.0.1:7860`.

## Tests

```powershell
python -m pytest python/tests/ -v
cd frontend
npm ci
npx tsc -b --noEmit
npm test -- --run
npm run build
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:7860"
npm run smoke
```

## Backtests

Historical validation runs only on real labels/snapshots.

```powershell
mlb-show-terminal snapshot-live-cards --uuids watchlist.txt --snapshot-id pre-2026-05-13 --output artifacts/history/pre.csv --enrich-mlb-stats
mlb-show-terminal snapshot-live-cards --uuids watchlist.txt --snapshot-id post-2026-05-20 --output artifacts/history/post.csv --enrich-mlb-stats
mlb-show-terminal backfill-upgrades --pre artifacts/history/pre.csv --post artifacts/history/post.csv --output-dir artifacts/history/backfill-2026-05-20
```

If those files do not exist yet, backtest status remains unavailable. The framework is present and deterministic, but promotion above `UNVALIDATED` requires enough real snapshots and outcomes.

Composite strategy backtests are available at `/api/backtest/strategy`. They return `INSUFFICIENT DATA` until enough timestamped real market snapshots exist.

Historical bid/ask snapshot backtests are available from The Show `price_history` payloads when the upstream listing includes enough daily history. These rows contain real historical `best_buy_price` and `best_sell_price`; the evaluator uses rolling-origin splits and future 1d/3d/7d rows as labels.

```powershell
mlb-show-terminal backtest-historical-snapshots --uuids watchlist.txt --output artifacts/history/historical-snapshot-backtest.json --min-snapshots 30 --lookback-snapshots 9 --horizons 1 3 7
```

API:

```powershell
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:7860/api/backtest/historical-snapshots -ContentType "application/json" -Body '{"uuids":["<card_uuid>"],"min_snapshots":30,"lookback_snapshots":9,"horizons_days":[1,3,7]}'
```

Completed-order historical backtests are available now from The Show listing payloads. These use real `completed_orders` sale timestamps/prices as historical sale snapshots. They do **not** infer historical bid/ask depth, so they validate directional hold behavior only; spread-flip historical validation still requires collected bid/ask snapshots.

```powershell
mlb-show-terminal backtest-completed-orders --uuids watchlist.txt --output artifacts/history/completed-orders-backtest.json --min-orders 30 --lookback-orders 20 --horizons 1 3 7
```

API:

```powershell
Invoke-WebRequest -UseBasicParsing -Method POST -Uri http://127.0.0.1:7860/api/backtest/completed-orders -ContentType "application/json" -Body '{"uuids":["<card_uuid>"],"min_orders":30,"lookback_orders":20,"horizons_days":[1,3,7]}'
```

The response includes `source_limitations`, `leakage_guard`, horizon metrics, deterministic baselines, `data_coverage_tier`, and `performance_validation_tier`. The legacy `validation_tier` field is retained for compatibility and mirrors `performance_validation_tier`. It will remain `UNVALIDATED` if the upstream payload lacks enough timestamped completed orders.

To search a broader bounded universe for retained official history, use:

```powershell
mlb-show-terminal collect-retained-history --rarities Diamond Gold Silver --per-rarity 15 --output artifacts/history/retained-market-discovery.json
```

This fetches real current listings, counts retained `price_history` bid/ask rows and `completed_orders` sale prints, and writes a summary plus backtest outputs. Use `--include-rows` only when you need a local inspectable artifact of the upstream rows; otherwise the command stores summary metrics only.

Realized ledger outcomes are not public market data. Import user-authored or account-exported fills with:

```powershell
mlb-show-terminal ledger-import-summary --input artifacts/history/ledger.csv --output artifacts/history/ledger-summary.json --source-name user_export
```

Supported columns include `card_uuid`, `card_name`, `buy_price`, `sell_price`, `timestamp`, `strategy_type`, `expected_net_stubs`, `tax`, `slippage`, and fill/holding-time fields. Missing required fields are reported; they are not fabricated.

## Validation Tiers

The API separates sample depth from proof of profitable performance:

- `data_coverage_tier`: how much real history exists.
- `performance_validation_tier`: whether the strategy beats after-tax baselines with calibration evidence.
- `validation_tier`: compatibility alias for `performance_validation_tier`.

Coverage tiers:

- `UNVALIDATED`: insufficient real history.
- `BRONZE`: minimal historical coverage; informational only.
- `SILVER`: moderate sample depth.
- `GOLD`: robust sample depth.
- `PLATINUM`: very large retained sample depth.

Performance tiers:

- `UNVALIDATED`: no usable performance evidence.
- `BRONZE`: limited or losing evidence; no production confidence.
- `SILVER`: positive after-tax performance with baseline comparison, but not fully calibrated.
- `GOLD`: robust, stable after-cost backtest with calibration evidence.
- `PLATINUM`: robust, calibrated, stable across periods, and beats baselines after costs.

This sprint does not claim production profitability. Retained-history testing has shown that a strategy can have `SILVER` data coverage while still losing stubs after tax; in that case the performance tier stays low and the model remains limited-use/data-collection only.

## UI

The React terminal has 10 top-level tabs:

1. Command Center
2. Market Scanner
3. Target / Trade Ticket
4. Strategy Matrix
5. Forecast Lab
6. Backtesting & Validation
7. Execution Ledger
8. Risk & Inventory
9. Data Provenance & Audit
10. README / Operations

Mobile uses a section selector instead of the crowded tab bar. Tables scroll horizontally with sticky first columns. The target card has a restrained CSS 3D treatment that is disabled under reduced motion.

## Deploy To Hugging Face

```powershell
python -m pip install -e ".[deploy]"
$env:HF_TOKEN = "<write token>"
python scripts/publish_hf_space.py --repo-id jviola1019/mlb-show-investment-terminal
```

The deploy bundle excludes `node_modules`, build outputs, caches, and test artifacts.

## Known Limitations

- Full historical spread-flip validation is unavailable until enough real bid/ask snapshots are collected.
- Completed-order backtests can validate directional hold behavior from real historical sale prices, but cannot prove spread-fill execution.
- Public realized fill outcomes are not broadly available; execution validation depends on user-provided ledger exports or manual trade logs.
- The Show API rate limits can slow live scans.
- Completed-order history is only as complete as the upstream provider returns.
- Supabase writes are disabled unless server-side credentials are configured.
- No output guarantees profit; all actions are after-tax/friction estimates, not fills.

## Example Workflow

1. Run a scan in Market Scanner.
2. Open a target row.
3. Read `Final Action` first.
4. If action is `INSTANT FLIP ONLY`, buy only when you can immediately relist and exit.
5. If action is `SPECULATIVE HOLD` or directional `INVESTABLE`, hold up to the stated horizon unless risk/exit gates trigger first.
6. Log the trade in Execution Ledger.
7. Compare expected stubs versus realized stubs before increasing size.

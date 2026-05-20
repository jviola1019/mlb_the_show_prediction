---
title: MLB Show Investment Terminal
emoji: "📈"
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
---

# MLB Show Investment Terminal

Docker Space deployment for the React + FastAPI trading terminal.

Python owns the strategy ontology, forecast governance, inventory risk, final action matrix, The Show price-history bid/ask backtests, and completed-order historical sale-snapshot backtests. React renders the terminal only. Supabase credentials, when used, must be configured as server-side Space secrets; no service credential is exposed to browser code.

The historical snapshot backtest uses real The Show `price_history` bid/ask rows when available. The completed-order backtest uses real The Show `completed_orders` timestamps/prices for directional hold validation. It does not infer historical bid/ask depth from sale prints.

Validation output separates `data_coverage_tier` from `performance_validation_tier`. A Space can have enough retained rows for nontrivial coverage while still remaining limited-use if the after-tax strategy loses money or lacks calibration evidence.

Required production secrets:

- `SUPABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_KEY`, or `SUPABASE_DB_URL` with `psycopg` available.
- `TERMINAL_WRITE_TOKEN` or `MLB_SHOW_WRITE_TOKEN` for trusted HTTP writes.
- `TERMINAL_CORS_ORIGINS` or `MLB_SHOW_CORS_ORIGINS` if the default localhost/Hugging Face allowlist is not sufficient.

Without Supabase secrets, the Space intentionally runs in read-only degraded mode and `/api/persistence/status` reports disabled writes.

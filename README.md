# MLB · INVESTMENT TERMINAL

Server-side R Shiny app for quantitative analysis of the MLB The Show 26
in-game card market. Live data only — no synthetic prices ever shipped to
the user. Every recommendation is gated behind 6 statistical-validation
checks; the app refuses to publish an action verb when validation fails.

## What it does

Four tabs:

- **CARD** — search → load a UUID from `mlb26.theshow.com/apis/listing.json`
  → block-bootstrap forecast cone (Politis-Romano stationary, 1500 sims)
  → multi-horizon EV table with 10% market tax + bid/ask spread → walk-forward
  CV with isotonic calibration → recommendation with explicit verdict tier.
- **OVR PRED** — live MLB Stats API (statsapi.mlb.com) recent (14d) vs
  season splits → z-score → ΔOVR → ΔPrice% with rarity-band boundary
detection (Bronze→Silver at OVR 75, Silver→Gold at 80, Gold→Diamond at 85).
- **MARKET SCAN** — discover top Diamonds live, run the full pipeline on
each, and publish ranked TOP BUY / TOP SELL leaderboards. Cards that
fail validation gates 1-4 are silently dropped; cards that fail only
gates 5-6 surface in OBSERVATIONAL ONLY (direction shown, no action).
- **VALIDATE** — walk-forward CV on the loaded card with block-residual
  or per-trade bootstrap CIs.
- **METHOD** — full quant pipeline + recommendation rubric documented.

## Statistical governance (the Phase F audit)

A polished interface with unvalidated EV is worse than an ugly honest
tool. Every CARD-tab recommendation passes through six gates:

| # | Gate | Failure response |
|---|------|------------------|
| 1 | `schema_valid` — listing has UUID, ask/bid > 0, ≥ 8 completed_orders | NOT INVESTABLE → ABSTAIN; EV table blanked |
| 2 | `history_sufficient` — ≥ max(50, 6 × horizon) price points | NOT INVESTABLE → ABSTAIN |
| 3 | `data_fresh` — most recent tick within 48 hours | NOT INVESTABLE → ABSTAIN |
| 4 | `cv_available` — walk-forward CV produced ≥ 30 trades | NOT INVESTABLE → ABSTAIN |
| 5 | `cv_skill_not_negative_sig` — IC upper-CI bound ≥ 0 (no significant anti-skill) | OBSERVATIONAL ONLY (direction shown, no action verb) |
| 6 | `ci_width_acceptable` — Brier CI width ≤ 0.20 AND IC CI width ≤ 0.50 | OBSERVATIONAL ONLY |

Verdict tiers:

- **INVESTABLE** — all 6 gates pass, full recommendation rendered.
- **OBSERVATIONAL ONLY** — gates 1–4 pass, 5 or 6 fails. Direction shown
  (▲ / ▼), action verb suppressed.
- **NOT INVESTABLE** — any of gates 1–4 fails. ABSTAIN verdict, EV table
  cells blanked, failing gates listed by name.

The MARKET SCAN leaderboards never include a card whose verdict is NOT
INVESTABLE. OBSERVATIONAL cards appear in their own table with the
failing gate explicitly named.

The optional Anthropic LLM cross-check (claude-opus-4-7) is badged
**NOT A SIGNAL · COMMENTARY ONLY**. It can interpret the metrics; it can
never approve a trade.

## Reproduce locally

```r
# in repo root
shiny::runApp(".\", port = 3838, host = "127.0.0.1", launch.browser = FALSE)
# then http://127.0.0.1:3838
```

Required R packages (DESCRIPTION declares all):
shiny, bslib, bsicons, shinybusy, httr2, jsonlite, dplyr, plotly,
reactable, boot, sandwich, probably, yardstick, rsample, memoise,
cachem, lubridate. Optional: np (Politis-White b.star), withr (tests).

Tests:
```r
testthat::test_dir("tests/testthat", reporter = "summary")
# 11 files, 189 assertions, 1 skip (CI-only walk-forward coverage)
```

Live API smoke (real network):
```r
source("R/utils.R"); source("R/api_theshow.R")
res <- search_card("Mike Trout")
stopifnot(length(res$listings) > 0)
stopifnot(all(grepl("^[a-f0-9]{32}$",
  sapply(res$listings, function(x) x$item$uuid))))
```

## Reproduce in Docker

```bash
docker build -t mlb-show-terminal .
docker run --rm -p 3838:3838 mlb-show-terminal
# http://localhost:3838
```

## Deploy to shinyapps.io

```r
# fill .Renviron from .Renviron.template
Rscript deploy.R
```

Free-tier limit: 25 active hours/month. Memoised API caches reset on
restart. The Show: 10-minute TTL on listings/listing.json. MLB Stats:
1-hour TTL.

## Repo layout

```
app.R                      entry point, sources every R/*.R
R/quant_*.R                bootstrap, regression, calibration,
                           walkforward, recommendation, ovr_predictor,
                           validation, scan
R/api_*.R                  theshow, mlb_stats, anthropic
R/ui_*.R + R/server_*.R    five tabs (card, ovr, scan, validate, method)
R/utils.R                  normalize_name, fmt_*, log_returns, %||%
www/                       theme.css + particles/transitions/viewport JS
data/roster_updates.rds    2026 roster-update calendar
data-raw/generate_data.R   regenerates roster_updates.rds
tests/testthat/            11 files
Dockerfile                 rocker/shiny:4.4 base, renv::restore
deploy.R                   single-function shinyapps deploy
.github/workflows/         R-CMD-check on push, deploy on push to main
```

## What this app deliberately does NOT do

- Generate or display synthetic prices anywhere in the user-facing path.
- Publish an action verb without passing all 6 validation gates.
- Treat the LLM as a statistical validator.
- Persist any state to disk during a session (caches are in-memory only).
- Bundle hard-coded UUIDs (they shift per game year and per attribute
  update). The MARKET SCAN tab discovers the universe live.

## License

MIT — see LICENSE.
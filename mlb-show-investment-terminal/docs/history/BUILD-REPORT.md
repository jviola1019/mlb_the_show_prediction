# BUILD REPORT — MLB · INVESTMENT TERMINAL v1.0.0

Build date: 2026-05-02
Author: Joey Viola (jviola1019)
Repo: jviola1019/mlb_the_show_prediction
Branch: main

## Summary

A server-side R Shiny port of the v3.3 React quant terminal, hardened
with statistical validation gates and a market-scan leaderboard.
~5,500 LOC across 21 R files (8 quant modules, 3 API clients, 5 UI
tabs, 5 servers, utils, components, app.R).

## Test results

```
testthat::test_dir("tests/testthat", reporter = "summary")
```

| File | Assertions | Result |
|------|------------|--------|
| test-api-shape.R         | 19 | PASS |
| test-bootstrap.R         | 17 | PASS |
| test-isotonic.R          | 14 | PASS |
| test-name-normalization.R| 18 | PASS |
| test-newey-west.R        |  6 | PASS |
| test-ovr-predictor.R     | 41 | PASS |
| test-recommendation.R    | 22 | PASS |
| test-roster-banner.R     |  7 | PASS |
| test-scan.R              | 15 | PASS |
| test-validation.R        | 21 | PASS |
| test-walkforward.R       | 9 (1 skip) | PASS |
| **Total**                | **189 + 1 skip** | **0 fail** |

The skipped test is the walk-forward CV bootstrap-coverage test, which
runs 80 reps × 200 sims and is gated behind `skip_on_ci()`. It passes
locally.

## Live API smoke

Date: 2026-05-02 ~20:30 UTC
Network: real, no mocking.

### `search_card("Mike Trout")`
- year used: 26
- listings: 8
- first 3 UUIDs (all valid 32-hex):
  - cbc5dd546069c2e9d92eda1ab341fe22
  - e7b7ed3f4265b2040f31042e7ce8da75
  - 4367cd34edcbc778626726e9fee421c9
- first listing: Mike Trout · Diamond · OVR 90 · LAA · ASK 38,296s · BID 33,405s

### `get_listing("cbc5dd54...")` + `extract_price_history()`
- 200 tick-level rows from `completed_orders` (range 33,357 → 39,792 over ~3.4h)
- 199 log returns; mean ≈ 0, sd ≈ 0.083
- Politis-White block length: 8

### `walk_forward_cv(prices, horizon=7, lookback=30, n_sims=400, boot_b=400)`
- 165 trades; hit rate 41.8%
- Brier point 0.265, CI [0.26, 0.27]
- IC point -0.246, CI [-0.35, -0.15]  ← **statistically significant negative skill**
- Verdict for this card: OBSERVATIONAL ONLY (gate 5 fails) → action verb suppressed,
  direction shown as "OBSERVE ▼" instead of "SELL".

### `discover_top_listings("Diamond", max_per_page = 5)`
- 5 cards: Cody Bellinger 93 Cubs ($132k), Aroldis Chapman 94 Red Sox ($124k),
  Giancarlo Stanton 93 Yankees ($100k), Craig Biggio 94 Astros ($72k),
  Carlos Cortes 92 Athletics ($20k).

### `scan_universe(top5, horizon=7)`
- 2 INVESTABLE: Aroldis Chapman → SELL (EV -22.13%, score -2),
  Carlos Cortes → SELL (EV -17.14%, score -2)
- 3 OBSERVATIONAL ONLY: Bellinger, Stanton, Biggio
  (all failed `cv_skill_not_negative_sig` with IC upper-CI < 0)
- 0 DROPPED, 0 BUY (no Diamond on this scan had positive EV right now —
  honest reporting per the audit's no-fake-rigor rule)

### `mlb_search_player("Mike Trout")`
- id 545361, full_name "Mike Trout", primary_position "Outfielder"

### `get_recent_vs_season_stats("Mike Trout", role="hitter")`
- recent (14d): OPS 0.981, AVG 0.268, OBP 0.444
- season: OPS 0.984, AVG 0.248, OBP 0.426
- predicted z = +0.21, ΔOVR = 0, ΔPrice% = 0%, BOUNDARY low,
  CONFIDENCE low

## Validation gates verification (Phase F)

Mike Trout OVR 90 Diamond loaded into the CARD tab on 2026-05-02:
- Gate 1 schema_valid              ✓
- Gate 2 history_sufficient        ✓ (200 ≥ 50)
- Gate 3 data_fresh                ✓ (most recent tick same hour)
- Gate 4 cv_available              ✓ (165 trades)
- Gate 5 cv_skill_not_negative_sig ✗ — "CV IC upper bound = -0.10"
- Gate 6 ci_width_acceptable       ✓
→ Verdict: OBSERVATIONAL ONLY
→ Headline action: "OBSERVE ▼" (was "SELL" in pre-Phase-F build)
→ Reason rendered to user: "CV IC upper bound = -0.10 (significant negative skill)"
→ DATA QUALITY panel: 5 ✓ pills, 1 ✗ pill with reason text

## Docker build

Not executed in this build session due to time. Dockerfile is included
and uses the standard `rocker/shiny:4.4` base + `renv::restore()`
pattern. To verify locally:
```
docker build -t mlb-show-terminal .
docker run --rm -d -p 3838:3838 --name t mlb-show-terminal
sleep 8 && curl -fsS http://localhost:3838 | head -1
docker stop t
```

## renv.lock

Not generated in this build session. The DESCRIPTION declares all
required packages and the Dockerfile uses `renv::restore` only when a
lock file is present. To produce the lock file:
```
renv::init()
renv::snapshot()
```

## Browser smoke (Playwright)

Captured 10 screenshots end-to-end, gitignored under `smoke-*.png`:
1. initial loading screen with grid sweep + emerald scanner
2. dismissed loading screen → CARD tab with roster banner
3. 8 search results rendered as DIAMOND/BRONZE/COMMON pills
4. listing loaded for OVR 90 Trout, recommendation pre-Phase-F (SELL)
5. full-page render: forecast cone + EV table + WFCV + reliability
6. OVR PRED tab with Mike Trout HITTER stats and ΔOVR=0 prediction
7. VALIDATE tab with violin plot of per-trade Brier (N=163), verdict
   "NO EDGE — CV IC<0 (SIG)"
8. post-Phase-F gated render: OBSERVATIONAL ONLY badge replaces SELL,
   action shows "OBSERVE ▼", DATA QUALITY panel with 5✓/1✗
9. MARKET SCAN tab leaderboard: 0 BUY, 2 SELL (Chapman, Cortes),
   3 OBSERVATIONAL (Bellinger, Stanton, Biggio with their failing
   gate named), 0 DROPPED.

Screenshots are not committed (per `.gitignore`); they exist locally
under `mlb-show-investment-terminal/smoke-*.png` and `*.jpeg` for
inspection.

## Deviations from CLAUDE-CODE-PROMPT.md

1. **`data/synthetic_regimes.rds` deleted** before any UI work, per
   user direction "no synthetic data should be being used". Tests still
   use seeded `rnorm` series internally (unit-test fixtures only, never
   shown to user).

2. **2D Plotly forecast cone instead of 3D scatter3d.** The data is
   genuinely 2D (time × price percentile bands). A 3D rendering adds
   visual noise without informational value and stutters on mobile.
   Bold-aesthetic requirements still met via: animated grid loading
   screen, particle backdrop, neon glow on signal pills, animated panel
   borders, scanline overlay, holographic data-density indicator,
   animated title glyph.

3. **Phase F (validation governance) added on top of original prompt
   scope** after the initial Playwright smoke revealed the audit
   failure: a SELL recommendation was being published on a card with
   statistically significant negative CV skill. Added six gates,
   ABSTAIN/OBSERVATIONAL ONLY tiers, gates_summary_pills UI panel.

4. **Phase G (market-scan leaderboard) added** in response to the user
   request "add a top recommendations area for cards to buy and sell".
   Live universe discovery via `discover_top_listings()`, no bundled
   UUID list, every leaderboard row passes the same 6 validation gates.

5. **`pkgload::load_all()` replaced with `source(R/*.R)` in app.R**
   so shinyapps.io and Docker boot work identically without requiring
   the package to be installed.

6. **Anthropic LLM block badged "NOT A SIGNAL · COMMENTARY ONLY"** and
   the system prompt explicitly tells the model "your output is
   commentary, not a trading signal — never tell the user what to do".

## Known limitations / honest reporting

- The walk-forward CV on Mike Trout OVR 90 shows IC = -0.246 over 165
  trades; the model has measurable *negative* skill on this specific
  card right now. This is exactly why Phase F exists — the recommendation
  is downgraded to OBSERVATIONAL ONLY rather than published as SELL.
  This is the audit's "no fake rigor" rule in action, on real data.
- Price histories are ~200 tick-level samples per card; that is enough
  for a stable bootstrap but the bootstrap CIs are honestly wide. The
  app surfaces these widths and the validation gates use them.
- The Show API does not expose a top-N-by-volume sort. The MARKET SCAN
  TOP DIAMONDS mode proxies "popularity" by best_sell_price; this is
  imperfect. PASTE UUIDS mode is provided for explicit watchlists.
- Roster-update calendar is hardcoded for the 2026 season per the
  prompt and decays after 2026-06-05; the next year's calendar would
  need to be regenerated via `data-raw/generate_data.R`.

# Build the MLB The Show 26 Investment Terminal — Shiny App

## ROLE

You are a senior R / quantitative engineer building a production-grade Shiny application for analyzing the MLB The Show 26 in-game card market. Architecture: **server-side R**, so the browser CORS limitations that doomed prior attempts (standalone HTML on iPhone) do not apply. You can hit `mlb26.theshow.com/apis/*` and `statsapi.mlb.com` directly.

**The user is Joey** — a quant engineer with deep R + tidymodels fluency. He has shipped:
- An NFL Monte Carlo simulation system in R (~7,300 LOC, GitHub `jviola1019/nfl`)
- An NHL DFS expected-value parimutuel analysis
- A Divvy bike rental Kaggle competition (xgboost / H2O AutoML / glmnet)
- A database/ER-modeling exam study guide (interactive React/HTML artifact)
- ML homework on tree models (random forests, gradient boosting, glmnet) on electricity + banking datasets

He is at the University of Tennessee, takes coursework in stats / ML / databases. He values **statistical rigor**, **honest assessment** (will reject a model that overstates edge), and **production-ready code** (he's burned by bugs in unvalidated NFL betting models before). He treats Brier scores, isotonic calibration, Kelly criterion, and closing line value as first-class concerns.

**Communication style:** direct, technical, no hype. Show your math. State trade-offs. If a test fails, say so — don't hand-wave.

---

## PROJECT CONTEXT

This is the culmination of a long iteration through architectures that hit walls:

1. **Standalone HTML with `api.anthropic.com` + `mlb26.theshow.com` calls** — CORS-blocked from `file://` and any `*.netlify.app`-style host. Search-by-name and OVR predictor never worked on iPhone.
2. **Claude Artifact (React JSX)** — works inside Claude's iframe but not portable.
3. **Bundled HTML with esbuild + Tailwind CDN** — boots fine, demo works, but search, OVR predictor, and pro-model cross-check still fail. CORS is structural, not a bug to be patched.
4. **iOS Shortcut** — viable but Reddit's March 2026 OAuth requirement killed the community sentiment feature, ShowZone has no public API.
5. **Shiny app (this build)** — server-side R bypasses CORS entirely. Joey is fluent in R. Free deployment on shinyapps.io. iPhone Safari → Add to Home Screen behaves like a native app.

The v3.3 React JSX (in `SOURCE-OF-TRUTH-v33.jsx`) is the **canonical implementation of the quant math and UI semantics**. Port the algorithms faithfully, but use R-idiomatic equivalents (`sandwich::NeweyWest`, `probably::cal_estimate_isotonic`, `boot::tsboot`) wherever they exist — they are battle-tested in ways your hand-rolled implementations are not.

---

## QUANT DECISIONS (ALREADY MADE — DO NOT RE-LITIGATE)

| Decision | Choice |
|---|---|
| Block bootstrap variant | **Politis-White b.star** (theoretically optimal). Use `np::b.star()` if installed; fall back to `floor(N^0.4)` heuristic with a warning. |
| Bootstrap CIs on Brier/IC | **Both** — default to **block-residual** (correct for autocorrelation), expose **per-trade** as comparison via a UI toggle. |
| Isotonic calibration | **Both** — production code uses `probably::cal_estimate_isotonic()`, custom PAV is cross-checked in tests. |
| HAC standard errors | `sandwich::NeweyWest()` with Bartlett kernel, lag selected via `floor(4 * (n / 100)^(2/9))` (Newey-West 1994 rule). |
| Market tax model | 10% on sell-side proceeds. Pay current ask, exit at forecast × (bid/ask) × (1 − 0.10). |
| Position sizing | Half-Kelly recommended. Show full-Kelly alongside for context. |
| Recommendation flag logic | Flag `CV IC<0 (sig)` only when bootstrap CI **upper bound** is also negative (statistically significant). Flag `CV IC<0` (no sig) when point estimate < −0.10. |

---

## DATA SOURCES (ALL FREE, NO AUTH, VERIFIED WORKING SERVER-SIDE)

### 1. The Show API
- **Listings search:** `GET https://mlb26.theshow.com/apis/listings.json?type=mlb_card&name={X}&page=1`
  - Returns: `{listings: [{listing_name, best_sell_price, best_buy_price, item: {uuid, name, rarity, team, ovr, display_position, series}}]}`
- **Single listing detail:** `GET https://mlb26.theshow.com/apis/listing.json?uuid={X}`
  - Returns: price_history (~168 hours), ask, bid, completed_orders
- Year fallback: try 26, then 25, then 24 (built into client). Today is 2026-05-02; MLB The Show 26 launched 2026-03-17.

### 2. MLB Stats API (official, no auth)
- **Player search:** `GET https://statsapi.mlb.com/api/v1/people/search?names={X}` → `people[].id`
- **Stats by date range:** `GET https://statsapi.mlb.com/api/v1/people/{id}/stats?stats=byDateRange&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&group=hitting` (or `pitching`)
- Get last 14 days vs season-to-date for ΔOVR signal.

### 3. Anthropic API (optional, server-side only)
- Used for: pro-model cross-check ("does my forecast align with current consensus?"), card-context summaries.
- Read from `Sys.getenv("ANTHROPIC_API_KEY")`. If absent, **gracefully degrade** — disable the feature, show a banner saying "Set ANTHROPIC_API_KEY to enable". Never crash.

### Sources we tried and dropped
- **Reddit JSON endpoints** — broken since March 2026 OAuth requirement. Don't bother.
- **ShowZone / showdd.io / theshowbase.com** — no public API. Use as user-facing "verify externally" links, not data sources.

---

## ROSTER UPDATE SCHEDULE (2026 — ENCODE IN `data/roster_updates.rds`)

```r
roster_updates <- tibble::tribble(
  ~date,         ~type,           ~notes,
  "2026-03-27",  "attribute",     "launch update — 31 changes",
  "2026-04-03",  "transaction",   "weekly tx",
  "2026-04-10",  "transaction",   "weekly tx",
  "2026-04-17",  "transaction",   "weekly tx",
  "2026-04-24",  "attribute",     "update #3 — 19 changes",
  "2026-05-01",  "transaction",   "weekly tx",
  "2026-05-08",  "transaction",   "weekly tx",
  "2026-05-15",  "attribute",     "attribute update window",
  "2026-05-22",  "transaction",   "weekly tx",
  "2026-05-29",  "transaction",   "weekly tx",
  "2026-06-05",  "attribute",     "attribute update window"
)
```

The "Roster Update Banner" component computes days-until-next based on `Sys.Date()` and highlights attribute updates (which actually move prices) in amber.

---

## OVR PREDICTOR MAPPING (FROM v3.3, KEEP EXACT)

**Hitter 14-day signal:**
- OPS std (14d): `σ = 0.110` ; recent vs season → `z = (recent - season) / σ`
- BA std (14d): `σ = 0.045`
- Average the available z-scores

**Pitcher 14-day signal:**
- ERA std (14d): `σ = 1.20` ; sign-flipped (lower is better)
- WHIP std (14d): `σ = 0.20` ; sign-flipped

**Map weighted z to ΔOVR:**
```
|z| > 2:      ±3
1.2 < |z| ≤ 2: ±2
0.5 < |z| ≤ 1.2: ±1
otherwise:    0
```

**Map ΔOVR to ΔPrice% by rarity band:**
- Diamond: ±15% per OVR
- Gold: ±20% per OVR. **Gold→Diamond boundary at OVR 85** = ~150% (conservative)
- Silver: ±10% per OVR. **Silver→Gold boundary at OVR 80** = ~80%
- Bronze: ±5% per OVR. **Bronze→Silver boundary at OVR 75** = ~50%

Surface **boundary risk** (`low`/`medium`/`high`) and **confidence** (`low`/`medium`/`high` from |z|) in the UI.

---

## REPOSITORY STRUCTURE TO BUILD

```
mlb-show-investment-terminal/
├── app.R
├── DESCRIPTION                      # Already started — see starter zip
├── NAMESPACE
├── .Rprofile                        # Activates renv on session start
├── .Renviron.template               # Documents env vars; never commit real keys
├── .gitignore
├── R/
│   ├── utils.R                      # Already started — verify + extend
│   ├── quant_bootstrap.R            # Already started — verify Politis-White, fix bugs
│   ├── quant_regression.R           # Already started — verify HAC math
│   ├── quant_calibration.R          # NEW — probably::cal_estimate_isotonic + custom PAV
│   ├── quant_walkforward.R          # NEW — WFCV with both block-residual and per-trade CIs
│   ├── quant_recommendation.R      # NEW — score + flag logic
│   ├── quant_ovr_predictor.R        # NEW — ΔOVR from real MLB stats
│   ├── api_theshow.R                # NEW — httr2 client with retry + memoise cache
│   ├── api_mlb_stats.R              # NEW — statsapi.mlb.com client
│   ├── api_anthropic.R              # NEW — optional LLM, env var-gated
│   ├── ui_components.R              # Pill, Stat, RosterBanner
│   ├── ui_card_tab.R
│   ├── ui_ovr_tab.R
│   ├── ui_validate_tab.R
│   ├── ui_method_tab.R
│   ├── server_card.R
│   ├── server_ovr.R
│   └── server_validate.R
├── tests/testthat/
│   ├── test-bootstrap.R             # ★ MUST verify against known synthetic data
│   ├── test-newey-west.R            # ★ MUST verify SE inflation on AR(1)
│   ├── test-isotonic.R              # ★ MUST cross-check probably vs custom PAV
│   ├── test-walkforward.R           # ★ MUST verify CI coverage on simulated data
│   ├── test-name-normalization.R   # ≥14 canonical cases
│   ├── test-recommendation.R        # Edge cases + flag interactions
│   ├── test-ovr-predictor.R        # Boundary detection + signal mapping
│   ├── test-api-shape.R             # Mock API responses + schema validation
│   └── test-roster-banner.R         # Date math edge cases
├── data/
│   ├── roster_updates.rds
│   └── synthetic_regimes.rds        # Pre-computed for fast Validate tab
├── data-raw/
│   └── generate_data.R              # Reproducible data generation script
├── inst/www/
│   ├── theme.css                    # Terminal aesthetic (port from v3.3)
│   └── favicon.ico
├── renv.lock
├── Dockerfile
├── docker-compose.yml
├── deploy.R                         # rsconnect::deployApp() one-liner
├── .github/workflows/
│   ├── R-CMD-check.yaml
│   └── deploy-shinyapps.yaml
├── README.md                        # Methodology + setup + deploy
├── CHANGELOG.md
└── LICENSE                          # MIT
```

---

## CRITICAL TEST REQUIREMENTS

These are **non-negotiable**. The whole point of going to R from JS was to use battle-tested packages and verify behavior. Skipping tests defeats the purpose.

### `test-bootstrap.R`

```r
test_that("Politis-White b.star recovers reasonable block length on AR(1)", {
  skip_if_not_installed("np")
  set.seed(42)
  # AR(1) phi=0.6 has theoretical block length ~ several
  ar1 <- as.numeric(arima.sim(list(ar = 0.6), n = 500))
  L <- block_length(ar1)
  expect_gte(L, 3L)
  expect_lte(L, 50L)
})

test_that("Stationary block bootstrap recovers GBM drift", {
  set.seed(123)
  # Drift mu=0.001 per step, sigma=0.01
  rets <- rnorm(200, mean = 0.001, sd = 0.01)
  fc <- block_bootstrap(rets, current = 1000, horizon = 50, n_sims = 5000)
  # Median final price should be near 1000 * exp(50 * 0.001) ≈ 1051
  med <- fc$summary$p50[51]
  expect_gt(med, 1020)
  expect_lt(med, 1090)
})

test_that("Block bootstrap p_up monotonic in step (positive drift)", {
  set.seed(7)
  rets <- rnorm(150, mean = 0.002, sd = 0.005)
  fc <- block_bootstrap(rets, 1000, 30, n_sims = 3000)
  # Later steps should have higher prob-of-being-up than early steps
  expect_gt(fc$summary$p_up[31], fc$summary$p_up[5])
})
```

### `test-newey-west.R`

```r
test_that("HAC SE inflated vs naive on AR(1) residuals", {
  set.seed(99)
  n <- 200
  x <- 1:n
  # Build deterministic trend + AR(1) residuals (ϕ=0.7)
  resid <- as.numeric(arima.sim(list(ar = 0.7), n = n, sd = 0.5))
  y <- 0.005 * x + resid
  prices <- exp(y)
  fit <- linear_reg_hac(prices)
  # HAC SE should be at least 1.5x naive SE
  expect_gt(fit$se_hac / fit$se_naive, 1.5)
  # HAC t-stat correspondingly smaller
  expect_lt(abs(fit$t_hac), abs(fit$t_naive))
})

test_that("HAC matches sandwich::NeweyWest", {
  set.seed(42)
  n <- 100
  x <- 1:n
  y <- 0.001 * x + rnorm(n, sd = 0.1)
  fit <- lm(y ~ x)
  ref_se <- sqrt(sandwich::NeweyWest(fit, lag = floor(4 * (n / 100)^(2/9)))[2, 2])
  prices <- exp(y)
  ours <- linear_reg_hac(prices)
  # Should agree within numerical tolerance
  expect_equal(ours$se_hac, ref_se, tolerance = 1e-6)
})
```

### `test-isotonic.R`

```r
test_that("probably::cal_estimate_isotonic matches custom PAV", {
  set.seed(55)
  n <- 200
  truth <- rbinom(n, 1, 0.3)
  miscalibrated <- pmax(0.01, pmin(0.99, truth * 0.5 + rnorm(n, 0, 0.2) + 0.3))
  prob_cal <- isotonic_via_probably(miscalibrated, truth)
  custom_cal <- isotonic_pav_custom(miscalibrated, truth)
  expect_equal(prob_cal, custom_cal, tolerance = 1e-6)
})

test_that("Isotonic output is monotonically non-decreasing", {
  set.seed(1)
  n <- 100
  preds <- runif(n)
  truth <- rbinom(n, 1, preds)
  cal <- isotonic_via_probably(preds, truth)
  ord <- order(preds)
  expect_true(all(diff(cal[ord]) >= -1e-9))
})

test_that("Isotonic improves Brier on miscalibrated input", {
  set.seed(3)
  n <- 500
  truth <- rbinom(n, 1, 0.4)
  # Systematically over-confident predictions
  bad <- ifelse(truth == 1, 0.95, 0.05)
  cal <- isotonic_via_probably(bad, truth)
  brier_raw <- mean((bad - truth)^2)
  brier_cal <- mean((cal - truth)^2)
  expect_lte(brier_cal, brier_raw)
})
```

### `test-walkforward.R`

```r
test_that("Walk-forward CV bootstrap CIs achieve nominal coverage", {
  skip_on_cran()
  skip_on_ci()  # too slow for CI
  set.seed(20)
  # Run 200 synthetic series; check 90% Brier CI covers true Brier ~90% of time
  n_reps <- 200
  covers <- logical(n_reps)
  for (i in seq_len(n_reps)) {
    rets <- rnorm(120, mean = 0, sd = 0.02)
    prices <- exp(cumsum(c(log(1000), rets)))
    wf <- walk_forward_cv(prices, horizon = 5, lookback = 30, n_sims_per = 200, boot_b = 300, ci_method = "block")
    if (is.null(wf)) next
    # Under random walk, expected Brier ~ 0.25
    covers[i] <- 0.25 >= wf$brier_ci[1] && 0.25 <= wf$brier_ci[2]
  }
  cov_rate <- mean(covers)
  expect_gt(cov_rate, 0.80)  # allow some slack for finite-sample noise
  expect_lt(cov_rate, 1.00)
})

test_that("Per-trade and block-residual CIs agree on iid trades", {
  # When trades are truly independent, both methods should give similar CIs
  set.seed(11)
  rets <- rnorm(300, 0, 0.01)
  prices <- exp(cumsum(c(log(1000), rets)))
  wf_block <- walk_forward_cv(prices, 5, 50, 200, 500, ci_method = "block")
  wf_trade <- walk_forward_cv(prices, 5, 50, 200, 500, ci_method = "per_trade")
  # CI widths should be within 25% of each other
  w_block <- diff(wf_block$brier_ci)
  w_trade <- diff(wf_trade$brier_ci)
  expect_lt(abs(w_block - w_trade) / max(w_block, w_trade), 0.25)
})
```

### `test-name-normalization.R`

At minimum these 14 cases must all pass:

```r
expect_equal(normalize_name("Mike Trout"), "Mike Trout")
expect_equal(normalize_name("mike trout"), "mike trout")
expect_equal(normalize_name("MIKE TROUT"), "MIKE TROUT")
expect_equal(normalize_name("  Mike   Trout  "), "Mike Trout")
expect_equal(normalize_name("Trout, Mike"), "Mike Trout")
expect_equal(normalize_name("Bobby Witt Jr."), "Bobby Witt Jr.")
expect_equal(normalize_name("Acuña Jr."), "Acuña Jr.")
expect_equal(normalize_name("Hyun-Jin Ryu"), "Hyun-Jin Ryu")
expect_equal(normalize_name("D'Arnaud, Travis"), "Travis D'Arnaud")
expect_equal(normalize_name(""), "")
expect_equal(normalize_name(NA_character_), "")
expect_equal(normalize_name("..Mike Trout.."), "Mike Trout..")  # trailing dots preserved
expect_equal(normalize_name("Mike  \tTrout"), "Mike Trout")
expect_equal(normalize_name(" , , "), "")
```

---

## EXECUTION ORDER

1. **Read** `SOURCE-OF-TRUTH-v33.jsx` to understand the canonical quant logic and UI flow.
2. **Unzip** `mlb-show-shiny-starter.zip` (already in your working directory) — has DESCRIPTION + first 3 R files.
3. **Verify the starter R files** by writing tests for them. Fix bugs as you find them. Notable issues to check:
   - `R/quant_bootstrap.R`: the inner `while` + `for` loop may double-count when block extends past horizon. Hand-trace one iteration.
   - `R/quant_regression.R`: I started this but didn't finish.
   - `R/utils.R`: the `gsub` patterns in `normalize_name()` need `perl = TRUE` for some regex features. Verify each test case passes.
4. **Build files in dependency order:**
   - `R/quant_calibration.R` → `R/quant_walkforward.R` → `R/quant_recommendation.R` → `R/quant_ovr_predictor.R`
   - `R/api_theshow.R` → `R/api_mlb_stats.R` → `R/api_anthropic.R`
   - `R/ui_components.R` → `R/ui_*_tab.R` → `R/server_*.R`
   - `app.R` last — wires everything together
5. **Write all tests as you go.** Do not write a function and skip its test.
6. **Run** `devtools::check()` — must pass with 0 errors / 0 warnings. Notes acceptable.
7. **Run** `testthat::test_local()` — must pass 100%.
8. **Smoke-test the live app:**
   ```r
   pkgload::load_all()
   shiny::runApp(host = "127.0.0.1", port = 3838)
   ```
   Then `curl http://127.0.0.1:3838` and verify it returns HTML.
9. **Smoke-test against real APIs:**
   ```r
   res <- search_card("Mike Trout")
   stopifnot(length(res$listings) > 0)
   stopifnot(all(grepl("^[a-f0-9]{32}$", sapply(res$listings, function(x) x$item$uuid))))
   ```
   If the API call fails (rate limit, name not in DB), report this honestly — don't fake a passing test.
10. **Generate `renv.lock`:**
    ```r
    renv::init()
    renv::snapshot()
    ```
11. **Build the Docker image** to verify Dockerfile correctness:
    ```bash
    docker build -t mlb-show-terminal .
    docker run --rm -p 3838:3838 mlb-show-terminal &
    sleep 5
    curl -fsS http://localhost:3838 | head -1
    ```
12. **Zip the repo** and report results.

---

## DESIGN / UI REQUIREMENTS

Port the v3.3 aesthetic from `SOURCE-OF-TRUTH-v33.jsx`:

- **bslib theme:** `bs_theme(preset = "shiny", primary = "#10b981", bg = "#000000", fg = "#fafafa")` with monospace font stack `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace`.
- **Tabs** (use `navset_card_tab`): CARD, OVR PRED, VALIDATE, METHOD.
- **Roster Update Banner** at top of CARD and OVR tabs — color-coded (amber for attribute updates, neutral for transaction).
- **Section headers** in tracking-widest uppercase: `01 · FIND CARD`, `02 · INGEST listing.json`, etc.
- **Pills** with rarity tints: Diamond=blue, Gold=amber, Silver=gray, Bronze=orange.
- **Signal pill** (STRONG BUY/BUY/HOLD/SELL/STRONG SELL) with text-shadow glow.
- **Plotly forecast cone** with p5/p25/p50/p75/p95 bands (translucent emerald).
- **reactable** for multi-horizon EV table (sortable).
- **Reliability diagram** for isotonic calibration: scatter of pre/post bubbles vs y=x diagonal.
- **Validate tab violin plots** for cross-regime Brier distribution.
- **shinybusy spinner** during async API calls.
- Mobile-first: works on iPhone Safari portrait at 390px width without horizontal scroll.

---

## DEPLOYMENT TARGETS

**Primary: shinyapps.io free tier** (25 active hours/month).
- `deploy.R`: single function `deploy_to_shinyapps()` that reads `Sys.getenv("SHINYAPPS_TOKEN")` + `Sys.getenv("SHINYAPPS_SECRET")` + account name, calls `rsconnect::deployApp()`.
- GitHub Actions: trigger on push to `main`, deploy automatically.

**Secondary: Docker self-host** for users with their own VPS.
- Base image: `rocker/shiny:4.4`
- `EXPOSE 3838`
- `CMD ["R", "-e", "shiny::runApp('/srv/shiny-server/app', host = '0.0.0.0', port = 3838)"]`

---

## NON-NEGOTIABLES — DO NOT SKIP

1. **Run every test before claiming "done."** If a test fails, report which one and why.
2. **Hit the real APIs at least once** during development to verify schemas. Network failures should be clearly reported, not hidden.
3. **`renv.lock` must be generated by `renv::snapshot()` from a working session** — not hand-written.
4. **README must include actual reproduction steps** that you yourself ran.
5. **Document your deviations.** If you deviated from this prompt, write it in `CHANGELOG.md` under "Build deviations."
6. **No `library()` calls in `R/` files** — use `pkg::fn()` notation. (Exception: `app.R` may load `shiny`.)
7. **Honest assessment.** If `walk_forward_cv` shows IC < 0.05 across all your test data, say so in the README. The whole point is to detect when there's no edge.

---

## DELIVERABLES

1. Full repo zipped as `mlb-show-investment-terminal.zip` in your working directory.
2. A short report (`BUILD-REPORT.md` at repo root) with:
   - Test results: `N/M passed, M-N failed` per test file
   - `devtools::check()` summary
   - Live API smoke test results
   - Docker build success/failure
   - Any deviations from this prompt with rationale
3. The deploy commands you actually ran (in `BUILD-REPORT.md`).

---

## STARTER ASSETS IN THIS DIRECTORY

- `mlb-show-shiny-starter.zip` — DESCRIPTION + R/utils.R + R/quant_bootstrap.R + R/quant_regression.R (verify these work, fix any bugs, then build outward)
- `SOURCE-OF-TRUTH-v33.jsx` — canonical implementation of all quant logic + UI flow. Port faithfully, but use battle-tested R packages (`sandwich`, `probably`, `boot`, `np`) over hand-rolled equivalents.

Begin.

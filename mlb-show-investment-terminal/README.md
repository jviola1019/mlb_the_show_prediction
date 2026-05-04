# MLB · INVESTMENT TERMINAL

Server-side R Shiny app for quantitative analysis of the MLB The Show 26
in-game card market. Live data only — no synthetic prices ever shipped to
the user. Every recommendation is gated behind 6 statistical-validation
checks; the app refuses to publish an action verb when validation fails.

## What it does

Five tabs:

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
shiny::runApp(".", port = 3838, host = "127.0.0.1", launch.browser = FALSE)
# then http://127.0.0.1:3838
```

## Run in VS Code (full workflow)

Tested on Windows 11 + R 4.4/4.5 + VS Code 1.9x. Works the same on macOS/Linux
with shell paths swapped.

### One-time setup

1. **Install R** (≥ 4.4) — https://cran.r-project.org/. On Windows the installer
   adds `R.exe` and `Rscript.exe` to `C:\Program Files\R\R-4.5.x\bin\` — make
   sure that's on your PATH (or run `where R` to confirm).
2. **Install VS Code extensions** (Ctrl+Shift+X):
   - **R** (`REditorSupport.r`) — syntax, REPL, package install helpers.
   - **R Debugger** (`RDebugger.r-debugger`) — optional, for breakpoints.
   - **httpyac** *or* **REST Client** (optional) — handy for poking the
     mlb26.theshow.com endpoints from a `.http` file.
3. **Install the R helper packages** the VS Code R extension expects (one-time,
   in any R prompt):
   ```r
   install.packages(c("languageserver", "httpgd", "renv"))
   ```
4. **Clone and open the repo**:
   ```powershell
   git clone https://github.com/jviola1019/mlb_the_show_prediction.git
   code mlb_the_show_prediction\mlb-show-investment-terminal
   ```
5. **Restore dependencies** (uses the committed `renv.lock`, ~3-5 min first time):
   ```powershell
   Rscript -e "renv::restore(prompt = FALSE)"
   ```

### Daily run

From the integrated terminal in VS Code (`` Ctrl+` ``), with the working
directory at the repo root:

```powershell
Rscript -e "shiny::runApp('.', port = 3838, host = '127.0.0.1', launch.browser = TRUE)"
```

That opens your default browser at `http://127.0.0.1:3838`. Stop with
`Ctrl+C` in the terminal.

### Run with the R extension's REPL (no terminal flags)

1. `Ctrl+Shift+P` → **R: Create R Terminal** (creates an interactive R
   session inside VS Code).
2. In the R terminal:
   ```r
   shiny::runApp(".", port = 3838, host = "127.0.0.1", launch.browser = TRUE)
   ```
3. Edit `R/server_card.R` (or any other file) → save → in the R terminal hit
   `Ctrl+C` then re-run the line above. (Shiny does not auto-reload R/* files
   when sourced this way; restart the app on each change.)

### Run the test suite from VS Code

In the integrated terminal:
```powershell
Rscript -e "testthat::test_dir('tests/testthat', reporter = 'summary')"
```
Expected: `11 files · 189 assertions · 1 skip · 0 fail`.

### Live API smoke (real network, ~15s)

```powershell
Rscript -e "for (f in list.files('R', pattern='\\.R$', full.names=TRUE)) source(f); res <- search_card('Mike Trout'); stopifnot(length(res$listings) > 0); cat('listings:', length(res$listings), ' year:', res$year, '\n')"
```

### Optional: configure the LLM cross-check

1. Copy `.Renviron.template` → `.Renviron` (in the same folder as `app.R`).
2. Fill in `ANTHROPIC_API_KEY=sk-ant-…`.
3. Restart the app. The CARD tab's `LLM CROSS-CHECK` panel now renders a
   commentary paragraph from `claude-opus-4-7`. If the key is missing or the
   call fails, the panel just reads "Set ANTHROPIC_API_KEY to enable" — the
   app never crashes on a missing/bad key.

### One-click VS Code task (optional)

Save this as `.vscode/tasks.json` in the repo if you want `Ctrl+Shift+B` to
boot the app:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run Shiny app",
      "type": "shell",
      "command": "Rscript",
      "args": [
        "-e",
        "shiny::runApp('.', port = 3838, host = '127.0.0.1', launch.browser = TRUE)"
      ],
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": []
    },
    {
      "label": "Run testthat suite",
      "type": "shell",
      "command": "Rscript",
      "args": [
        "-e",
        "testthat::test_dir('tests/testthat', reporter='summary')"
      ],
      "group": "test",
      "problemMatcher": []
    }
  ]
}
```

### Troubleshooting

- **`Error: there is no package called 'shiny'`** — `renv::restore()` didn't
  finish. Re-run `Rscript -e "renv::restore(prompt = FALSE)"` and watch the tail.
- **App boots but the page is blank** — hard-refresh (`Ctrl+F5`); the boot
  screen self-dismisses 600 ms after Shiny connects, with a 2.5 s hard
  fallback in `www/viewport.js`.
- **`port 3838 already in use`** — another `Rscript` is still running. On
  Windows: `Get-Process Rscript | Stop-Process -Force` in PowerShell, then
  retry. Or just pick a different port: `... port = 3839, ...`.
- **MARKET SCAN tab returns "no rows" instantly** — discovery succeeded but
  every card landed in OBSERVATIONAL or DROPPED. Open the DROPPED panel for
  the failing-gate counts. This is correct, audit-aligned behavior, not a
  bug.
- **`np` not installed** — optional. The block-length selector falls back to
  `floor(N^0.4)` automatically. Install it if you want Politis-White b.star:
  `install.packages("np")`.

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

## Update / publish from RStudio (exact click path)

These are the exact RStudio steps for first-time publish AND for re-deploying
after edits. Tested on RStudio 2024.04+.

### One-time setup

1. **Tools → Global Options → Publishing → Connect → ShinyApps.io**.
2. In the dialog, paste the full `rsconnect::setAccountInfo(name=..., token=..., secret=...)`
   line from your shinyapps.io account page (top-right avatar → **Tokens** →
   **Show**). Click **Connect Account**.
3. Confirm the account now appears in the Publishing list as
   `<your-account>@shinyapps.io`.
4. **File → Open Project** → navigate to
   `mlb-show-investment-terminal/` (open the folder itself, not a `.Rproj`
   inside a parent — the project root must contain `app.R`).
5. In the R console:
   ```r
   renv::restore(prompt = FALSE)
   ```
   Wait for it to finish (~3-5 min the first time). The package list comes
   from the committed `renv.lock`.

### Publish (first deploy)

1. Open `app.R` in the editor.
2. Click the **blue Publish icon** in the editor toolbar (or **File →
   Publish…** → **Publish Document**).
3. **Publish to Server**: choose your `shinyapps.io` account.
4. **Files to publish**: tick exactly these and untick the rest —
   - `app.R`
   - `DESCRIPTION`
   - `NAMESPACE`
   - the entire `R/` folder
   - the entire `data/` folder
   - the entire `www/` folder
   - `renv.lock`
   - `.Rprofile`
   - `renv/activate.R`, `renv/settings.json` (RStudio shows them under
     `renv/` — keep them)
   - **DO NOT include**: `tests/`, `data-raw/`, `inst/`, `.playwright-mcp/`,
     `*.png`, `*.log`, `BUILD-REPORT.md`, `SPRINT-HARDENING-PROMPT.md`,
     `.Renviron` (this one is auto-excluded).
5. **Title**: `mlb-show-terminal` (this becomes the URL slug —
   `https://<account>.shinyapps.io/mlb-show-terminal/`).
6. Click **Publish**. RStudio will show a build log in the bottom pane;
   first build takes 8-12 minutes (it compiles every dependency from
   source). Subsequent deploys are <60 s because shinyapps caches the
   restored library.
7. When the log ends with `Application successfully deployed to
   https://...`, the URL opens in your browser. Submit that URL.

### Update (subsequent deploys, after editing any R/CSS/JS)

1. Save your edits in RStudio (`Ctrl+S`).
2. Run the test suite first — never publish red:
   ```r
   testthat::test_dir("tests/testthat", reporter = "summary")
   ```
   Expected: `12 files · 211 assertions · 2 skip · 0 fail`.
3. Click the same **blue Publish icon** in the `app.R` editor toolbar
   (RStudio remembers the previous selection).
4. The dialog opens with the previous file list pre-checked. Click
   **Publish** — no need to re-select files.
5. Build log shows `Updating application...` instead of a fresh build,
   so the deploy completes in 30-60 s.

### Add or rotate the LLM key without re-publishing

Don't put `ANTHROPIC_API_KEY` in `.Renviron` for shinyapps deploys — it
won't be read. Instead:

1. shinyapps.io dashboard → **Applications → mlb-show-terminal → Settings → Variables**.
2. Add `ANTHROPIC_API_KEY = sk-ant-…`. Save.
3. The next visitor's session reads it via `Sys.getenv()` automatically;
   no re-deploy needed.

### Common RStudio publish failures

- **"Token not authorized"** → re-run **Tools → Global Options → Publishing**
  and paste a fresh `setAccountInfo()` line; the old one expired.
- **"Application failed to start: cannot open file 'data/roster_updates.rds'"**
  → you forgot to tick the `data/` folder in the file list. Re-publish
  including it.
- **"deployment timed out"** → free-tier sleep killed the build. Click
  Publish again; second attempt almost always succeeds (the package
  restore is now cached).
- **App page is blank / spinner forever** → check **Applications →
  mlb-show-terminal → Logs**. Most common cause: missing CRAN package
  in `renv.lock`. Run `renv::snapshot(prompt = FALSE)` locally and
  re-publish.

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

# Changelog

## v1.0.0 — 2026-05-02

Initial release of the MLB · INVESTMENT TERMINAL.

### Highlights
- **Statistical governance**: every recommendation passes through 6
  validation gates (schema / history / freshness / CV available / CV skill
  not significantly negative / CI width acceptable). The app refuses to
  publish an action verb when any of gates 1-4 fail; downgrades to
  OBSERVATIONAL ONLY when only gates 5-6 fail. There is no "looks
  professional" path that bypasses validation.
- **Server-side R Shiny** — bypasses browser CORS that broke prior
  standalone-HTML and Claude-Artifact attempts.
- **CARD tab**: search → load by UUID → block-bootstrap forecast cone
  (1500 sims) → multi-horizon EV table (1d/3d/7d) → 7th panel walk-forward
  CV with isotonic calibration → recommendation with explicit verdict tier
  + DATA QUALITY gate panel.
- **OVR PRED tab**: live MLB Stats API (statsapi.mlb.com) recent-vs-season
  splits → z-score → ΔOVR → ΔPrice% with rarity-band boundary detection.
- **MARKET SCAN tab**: live `discover_top_listings()` → run the full
  pipeline on each UUID → filter to INVESTABLE → ranked TOP BUY / TOP
  SELL leaderboards. Cards that fail gate 5 or 6 are surfaced separately
  in OBSERVATIONAL ONLY with their failing gate explicitly named. No card
  appears on the BUY/SELL board unless all 6 gates pass.
- **VALIDATE tab**: walk-forward CV on the loaded card (no synthetic
  data) with block-residual or per-trade bootstrap CIs.
- **METHOD tab**: full pipeline + recommendation rubric documented.
- **LLM cross-check (optional)**: claude-opus-4-7 with prompt caching,
  env-gated, badged "NOT A SIGNAL · COMMENTARY ONLY" — the LLM never
  marks a trade valid.

### Quant
- Politis-Romano stationary block bootstrap with Politis-White b.star
  block-length selection (np::b.star), N^0.4 fallback.
- Newey-West HAC OLS via sandwich::NeweyWest (Bartlett kernel,
  floor(4*(N/100)^(2/9)) lag).
- Walk-forward CV with bootstrap CIs on Brier and IC: block-residual via
  boot::tsboot(sim="geom") or per-trade via boot::boot.
- Isotonic calibration via probably::cal_estimate_isotonic, cross-checked
  against custom PAVA at 1e-6 tolerance.
- 10% market tax + bid/ask spread baked into EV; half-Kelly sizing.

### Tests
11 testthat files, 189 assertions, 1 skip (CI-only walk-forward
coverage). All math verified before any UI was wired.

### Deviations from CLAUDE-CODE-PROMPT.md
- `data/synthetic_regimes.rds` was removed before any UI work began,
  per user instruction "no synthetic data should be being used". Tests
  still use seeded `rnorm` series internally to verify estimator
  properties (these are unit-test fixtures, never user-visible).
- Phase F (validation governance) and Phase G (market scan + top
  recommendations) were added on top of the original prompt scope after
  the initial Playwright smoke revealed an unguarded SELL recommendation
  on a card with significant negative CV skill.
- The forecast cone is rendered as a 2D Plotly with translucent emerald
  bands rather than a 3D scatter3d cone. The 2D form is genuinely more
  legible (the data is 2D — time × price) and renders without stutter on
  iPhone Safari at 390px. Bold-aesthetic requirements are still met
  through: animated grid loading screen, particle backdrop with
  prefers-reduced-motion + small-viewport guards, neon glow on signal
  pills, animated panel borders, scanline overlay, holographic
  data-density indicator.
# Archival Note

This changelog captures older pre-ontology work. Current strategy labels, validation tiers, persistence behavior, and deployment instructions are documented in `README.md`, `FINAL_AUDIT.md`, and `docs/parity/python-react-parity.md`.

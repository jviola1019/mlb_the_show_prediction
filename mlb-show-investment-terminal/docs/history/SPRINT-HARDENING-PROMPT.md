# CLAUDE CODE PLANNING AGENT PROMPT — MLB THE SHOW INVESTMENT TERMINAL FINAL HARDENING SPRINT

You are Claude Code acting as a multi-agent planning + implementation system.

Repository:
`jviola1019/mlb_the_show_prediction`

Project subdirectory appears to be:
`mlb-show-investment-terminal/`

Latest observed branch:
`main`

Latest observed commits:
- `fd4aab546dbbd213d05539d9796515e4319bfd98` — README update.
- `3876252f66fee936fc17a744068a7031b043f457` — renv bootstrap / ShinyApps metadata.
- `26a79ebf1c2ea7c0c5aad6577a4fb0520179abfc` — app/tests/workflows/renv.
- Earlier initial app commit: `d111e977265052ad488ffccce4028d9ffc3128fd`.

This sprint is not optional cleanup. Every issue below must be fixed in this sprint before completion.

---

## 0. Mission

Harden the MLB The Show Investment Terminal so the UI, statistics, and recommendation layer cannot overstate confidence.

The app currently has a strong foundation:
- Six validation gates exist in `R/quant_validation.R`.
- Verdicts exist:
  - `INVESTABLE`
  - `OBSERVATIONAL ONLY`
  - `NOT INVESTABLE`
- `NOT INVESTABLE` returns `ABSTAIN`.
- `OBSERVATIONAL ONLY` suppresses BUY/SELL into `OBSERVE ▲/▼`.
- EV table blanks values for `NOT INVESTABLE`.
- LLM cross-check is commentary-only.

But there are still serious governance leaks:
1. Forecast cone can still render normally with only `length(r) >= 8`, even when validation says `NOT INVESTABLE`.
2. EV table only blanks for `NOT INVESTABLE`; `OBSERVATIONAL ONLY` can still show Kelly/staking-like output.
3. The UI warning says “need ≥ 6×horizon” while the actual gate requires `max(50, 6×horizon)`.
4. Calibration absence is not represented as a distinct gate.
5. Recommendation scoring still internally produces BUY/SELL labels before governance suppression.
6. LLM cross-check does not receive enough explicit gate/verdict context.
7. README says “Four tabs” but lists five.
8. Professional graphic design needs to visually communicate validation state, not just look futuristic.
9. Tests must prove all of this, not merely assert function existence.

The goal is to finish the sprint with no remaining misleading forecast, EV, staking, or investment visuals under failed validation.

---

## 1. Required agents / roles

Use all appropriate Claude Code agents or equivalent internal task decomposition.

Required roles:

### 1. Quant Governance Agent
Owns:
- validation gates;
- model state;
- EV suppression;
- forecast actionability;
- calibration truthfulness;
- walk-forward CV validity;
- statistical documentation.

### 2. R/Shiny Engineering Agent
Owns:
- server reactivity;
- UI render gating;
- Shiny module cleanup;
- testable functions;
- app smoke reliability;
- no reactive crashes.

### 3. Testing / QA Agent
Owns:
- `testthat` tests;
- app smoke tests;
- edge-case fixtures;
- insufficient-history fixtures;
- calibration-missing fixtures;
- visual state assertions if possible.

### 4. Professional UI/UX + Graphic Design Agent
Owns:
- visual hierarchy;
- blocked-state design;
- badge styling;
- preventing misleading green/positive styling;
- terminal aesthetic without fake confidence;
- responsive and readable layout.

### 5. Security / LLM Governance Agent
Owns:
- `ANTHROPIC_API_KEY`;
- LLM commentary-only logic;
- no API key leakage;
- no LLM influence on statistical state;
- safe missing-key behavior.

### 6. Documentation Agent
Owns:
- README consistency;
- method docs;
- validation docs;
- limitations;
- changelog/sprint summary.

Planning agent must coordinate the agents and finish all implementation items before declaring done.

---

## 2. First step — inspect and run baseline

From repository root, run:

```bash
pwd
find . -maxdepth 5 -type f | sort
git status --short
git log --oneline -10
```
# Archival Note

This sprint prompt belongs to the older governance-only implementation. Current source-of-truth semantics are the strategy ontology and composite matrix documented in `README.md`, `FINAL_AUDIT.md`, and `docs/parity/python-react-parity.md`.

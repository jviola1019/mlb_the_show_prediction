# React/Shiny Parity Audit

Generated: 2026-05-08T17:20:41Z
Status: ok

| Feature | Group | Status | Shiny | React/Python |
| --- | --- | --- | --- | --- |
| market_scan.partitions | Market Scan | parity | `R/server_scan.R::scan_partition` | `frontend/src/tabs/ScanTab.tsx` / `python/mlb_show_terminal/scan.py::partition_scan` |
| market_scan.partition_columns | Market Scan | parity | `R/server_scan.R::render_table` | `frontend/src/components.tsx` / `python/mlb_show_terminal/scan.py::enrich_scan_fields` |
| market_scan.progress_jobs | Market Scan | parity | `R/server_scan.R::Progress` | `frontend/src/tabs/ScanTab.tsx` / `python/mlb_show_terminal/scan_jobs.py` |
| market_scan.uuid_parser | Market Scan | parity | `R/server_scan.R::scan_uuid_paste` | `frontend/src/uuid.ts` / `python/mlb_show_terminal/uuid_tools.py` |
| card.forecast_cone | Card Analysis | parity | `R/server_card.R::forecast plot` | `frontend/src/tabs/CardTab.tsx` / `python/mlb_show_terminal/forecast.py::forecast_cone` |
| card.walk_forward_cv | Card Analysis | parity | `R/server_card.R::walk_forward_cv` | `frontend/src/tabs/CardTab.tsx` / `python/mlb_show_terminal/forecast.py::walk_forward_cv` |
| validate.manual_flip | Validate | parity | `R/server_validate.R::manual flip` | `frontend/src/tabs/ValidateTab.tsx` / `python/mlb_show_terminal/market.py::validate_flip_formula` |
| overall.market_health | Overall | parity | `R/server_overall.R::overall_market_health` | `frontend/src/tabs/OverallTab.tsx` / `python/mlb_show_terminal/scan.py::_scan_summary` |

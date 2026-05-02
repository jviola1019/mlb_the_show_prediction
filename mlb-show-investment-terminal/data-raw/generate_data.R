#!/usr/bin/env Rscript
# Generate data/roster_updates.rds.
# Re-run anytime the schedule changes.
# NOTE: per user direction, no synthetic price data ships with the app.
# All validation tabs operate on real, live-fetched card price histories.

setwd(here::here())

# 1. Roster update schedule (2026)
roster_updates <- tibble::tribble(
  ~date,         ~type,           ~notes,
  "2026-03-27",  "attribute",     "launch update -- 31 changes",
  "2026-04-03",  "transaction",   "weekly tx",
  "2026-04-10",  "transaction",   "weekly tx",
  "2026-04-17",  "transaction",   "weekly tx",
  "2026-04-24",  "attribute",     "update #3 -- 19 changes",
  "2026-05-01",  "transaction",   "weekly tx",
  "2026-05-08",  "transaction",   "weekly tx",
  "2026-05-15",  "attribute",     "attribute update window",
  "2026-05-22",  "transaction",   "weekly tx",
  "2026-05-29",  "transaction",   "weekly tx",
  "2026-06-05",  "attribute",     "attribute update window"
)
roster_updates$date <- as.Date(roster_updates$date)
saveRDS(roster_updates, "data/roster_updates.rds")
cat("wrote data/roster_updates.rds (", nrow(roster_updates), "rows)\n")


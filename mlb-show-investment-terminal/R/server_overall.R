#' Server logic for the OVERALL dashboard tab.
#' Reads exclusively from `app_state` populated by the other servers.
#' @export
server_overall <- function(input, output, session, app_state) {

  output$overall_roster_banner <- shiny::renderUI({
    roster_banner(today = Sys.Date(), updates = app_state$roster_updates)
  })

  fmt_ts <- function(ts) {
    if (is.null(ts) || length(ts) == 0L) return("—")
    if (is.numeric(ts)) ts <- as.POSIXct(ts, origin = "1970-01-01")
    format(max(ts), "%Y-%m-%d %H:%M %Z")
  }

  output$overall_status_badge <- shiny::renderUI({
    log <- app_state$api_log
    last_ok  <- max(c(0, log$theshow_ok %||% 0))
    last_err <- max(c(0, log$theshow_err %||% 0))
    fresh_ok <- (Sys.time() - as.POSIXct(last_ok, origin = "1970-01-01")) <
      as.difftime(2, units = "hours") && last_ok > 0
    if (last_ok == 0 && last_err == 0) {
      pill("AWAITING FIRST FETCH", "neutral")
    } else if (last_err > last_ok) {
      pill("DEGRADED — last fetch failed", "warn")
    } else if (fresh_ok) {
      pill("HEALTHY", "bull")
    } else {
      pill("STALE — last fetch > 2h ago", "warn")
    }
  })

  output$overall_health_grid <- shiny::renderUI({
    log <- app_state$api_log
    htmltools::tags$div(class = "stat-grid stat-grid-3",
      stat("LAST THE SHOW OK",
           fmt_ts(log$theshow_ok %||% numeric(0))),
      stat("LAST THE SHOW ERR",
           fmt_ts(log$theshow_err %||% numeric(0))),
      stat("LAST MLB STATS OK",
           fmt_ts(log$mlb_ok %||% numeric(0))),
      stat("LAST MLB STATS ERR",
           fmt_ts(log$mlb_err %||% numeric(0))),
      stat("UUIDS LOADED THIS SESSION",
           as.character(length(app_state$loaded_uuids() %||% character(0)))),
      stat("APP TIME",
           format(Sys.time(), "%Y-%m-%d %H:%M %Z"))
    )
  })

  output$overall_scan_summary <- shiny::renderUI({
    df <- app_state$last_scan_df
    if (is.null(df) || nrow(df) == 0L) {
      return(htmltools::tags$div(class = "muted",
        "No scan run yet. Open MARKET SCAN and click SCAN UNIVERSE."))
    }
    n  <- nrow(df)
    n_inv <- sum(df$verdict_status == "INVESTABLE", na.rm = TRUE)
    n_obs <- sum(df$verdict_status == "OBSERVATIONAL ONLY", na.rm = TRUE)
    n_not <- sum(df$verdict_status == "NOT INVESTABLE", na.rm = TRUE)
    pass_rate <- if (n > 0L) n_inv / n else NA_real_
    htmltools::tags$div(class = "stat-grid stat-grid-3",
      stat("RUN AT",       fmt_ts(app_state$last_scan_at)),
      stat("CARDS SCANNED", as.character(n)),
      stat("INVESTABLE",   as.character(n_inv), tone = "bull"),
      stat("OBSERVATIONAL", as.character(n_obs), tone = "warn"),
      stat("NOT INVESTABLE", as.character(n_not), tone = "bear"),
      stat("VALIDATION PASS", fmt_pct(pass_rate))
    )
  })

  output$overall_tier_bar <- shiny::renderUI({
    df <- app_state$last_scan_df
    if (is.null(df) || nrow(df) == 0L || !"tier" %in% names(df)) {
      return(htmltools::tags$div(class = "muted",
        "Tier distribution appears after the next MARKET SCAN run."))
    }
    counts <- table(factor(df$tier,
                           levels = c("DIAMOND","GOLD","SILVER",
                                      "BRONZE","ABSTAIN")))
    htmltools::tags$div(class = "tier-bar",
      lapply(names(counts), function(t) {
        htmltools::tags$div(class = "stat-box",
          htmltools::tags$div(class = "stat-label", t),
          htmltools::tags$div(class = "stat-value",
                              as.character(counts[[t]])))
      })
    )
  })

  output$overall_market_health <- shiny::renderUI({
    df <- app_state$last_scan_df
    if (is.null(df) || nrow(df) == 0L) {
      return(htmltools::tags$div(class = "muted",
        "Run a MARKET SCAN to populate market-health medians."))
    }
    med_spread <- stats::median(df$spread_pct, na.rm = TRUE)
    med_n_trades <- stats::median(df$n_trades, na.rm = TRUE)
    med_brier_w <- stats::median(df$ic_ci_hi - df$ic_ci_lo, na.rm = TRUE)
    med_ic_p <- stats::median(df$ic_point, na.rm = TRUE)
    htmltools::tags$div(class = "stat-grid stat-grid-3",
      stat("MEDIAN SPREAD", fmt_pct(med_spread)),
      stat("MEDIAN n_trades", sprintf("%.0f", med_n_trades %||% NA)),
      stat("MEDIAN IC CI WIDTH", sprintf("%.2f", med_brier_w %||% NA)),
      stat("MEDIAN IC POINT", sprintf("%+.3f", med_ic_p %||% NA)),
      stat("CARDS WITH NEG SKILL",
           as.character(sum(!is.na(df$ic_ci_hi) & df$ic_ci_hi < 0))),
      stat("CARDS WITH POS SKILL",
           as.character(sum(!is.na(df$ic_ci_lo) & df$ic_ci_lo > 0)))
    )
  })
}

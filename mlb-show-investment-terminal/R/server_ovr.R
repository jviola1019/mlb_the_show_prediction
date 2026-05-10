#' Server logic for the OVR PRED tab.
#' @export
server_ovr <- function(input, output, session, app_state) {

  output$ovr_roster_banner <- shiny::renderUI({
    roster_banner(today = Sys.Date(), updates = app_state$roster_updates)
  })

  stats_bundle <- shiny::eventReactive(input$btn_ovr_load, {
    shiny::req(nchar(input$ovr_name) > 0)
    shinybusy::show_modal_spinner(spin = "atom", color = "#10b981",
                                  text = "fetching MLB stats...")
    on.exit(shinybusy::remove_modal_spinner(), add = TRUE)
    role <- if (input$ovr_role == "auto") NULL else input$ovr_role
    out <- tryCatch(get_recent_vs_season_stats(input$ovr_name, role = role,
                                               today = Sys.Date()),
                    error = function(e) NULL)
    now_n <- as.numeric(Sys.time())
    if (!is.null(out) && !is.null(out$player)) {
      app_state$api_log$mlb_ok <- c(app_state$api_log$mlb_ok, now_n)
    } else {
      app_state$api_log$mlb_err <- c(app_state$api_log$mlb_err, now_n)
    }
    out
  })

  output$ovr_stats_summary <- shiny::renderUI({
    s <- stats_bundle()
    shiny::req(s)
    if (is.null(s$player)) {
      return(htmltools::tags$div(class = "muted",
        sprintf("no player match for '%s' on statsapi.mlb.com",
                input$ovr_name)))
    }
    role <- s$role
    htmltools::tagList(
      htmltools::tags$div(class = "ingest-status",
        htmltools::tags$span(class = "sr-name", s$player$full_name),
        pill(toupper(role), if (role == "pitcher") "info" else "bull"),
        htmltools::tags$span(class = "muted",
                             s$player$primary_position)
      ),
      if (role == "hitter") {
        htmltools::tags$div(class = "stat-grid stat-grid-3",
          stat("OPS 14d",  sprintf("%.3f", s$recent$ops %||% NA),
               sub = sprintf("season %.3f", s$season$ops %||% NA)),
          stat("AVG 14d",  sprintf("%.3f", s$recent$avg %||% NA),
               sub = sprintf("season %.3f", s$season$avg %||% NA)),
          stat("PA 14d",  sprintf("%.0f",
                                  s$recent$plateAppearances %||%
                                    s$recent$atBats %||% NA),
               sub = sprintf("season %.0f",
                             s$season$plateAppearances %||%
                               s$season$atBats %||% NA))
        )
      } else {
        htmltools::tags$div(class = "stat-grid stat-grid-3",
          stat("ERA 14d",  sprintf("%.2f", s$recent$era %||% NA),
               sub = sprintf("season %.2f", s$season$era %||% NA)),
          stat("WHIP 14d", sprintf("%.2f", s$recent$whip %||% NA),
               sub = sprintf("season %.2f", s$season$whip %||% NA)),
          stat("IP 14d",   sprintf("%.1f", s$recent$inningsPitched %||% NA),
               sub = sprintf("season %.1f", s$season$inningsPitched %||% NA))
        )
      }
    )
  })

  output$ovr_prediction <- shiny::renderUI({
    s <- stats_bundle()
    shiny::req(s)
    if (is.null(s$player)) {
      return(htmltools::tags$div(class = "muted",
                                 "no player loaded"))
    }
    manual_new_rank <- suppressWarnings(as.numeric(input$ovr_new_rank))
    loaded_new_rank <- tryCatch(
      app_state$current_listing$item$new_rank %||% NA_real_,
      error = function(e) NA_real_
    )
    new_rank <- if (is.finite(manual_new_rank)) manual_new_rank
                else loaded_new_rank
    pred <- roster_upgrade_engine(
      stats_recent = s$recent,
      stats_season = s$season,
      role = s$role,
      current_ovr = input$ovr_current,
      rarity = input$ovr_rarity,
      new_rank = new_rank
    )
    py_score <- tryCatch(
      python_score_card(list(
        current_ovr = input$ovr_current,
        rarity = input$ovr_rarity,
        new_rank = new_rank,
        role = s$role,
        recent = s$recent,
        season = s$season,
        liquidity_score = 1,
        raw_ask = NA_real_,
        raw_bid = NA_real_
      )),
      error = function(e) NULL
    )
    py_pred <- tryCatch(python_result_to_upgrade(py_score),
                        error = function(e) NULL)
    if (!is.null(py_pred)) pred <- py_pred
    action_tone <- switch(pred$action,
      "BUY SPECULATIVE" = "bull",
      "WATCH" = "info",
      "SELL" = "bear",
      "AVOID" = "warn",
      "neutral"
    )
    htmltools::tagList(
      pill(pred$action, action_tone),
      htmltools::tags$div(class = "stat-grid stat-grid-3",
        stat("P(UPGRADE)", fmt_pct(pred$p_upgrade, 1)),
        stat("P(DOWNGRADE)", fmt_pct(pred$p_downgrade, 1)),
        stat("P(CROSS NEXT)", fmt_pct(pred$p_cross_next_threshold, 1),
             sub = sprintf("next %s", pred$next_threshold %||% NA)),
        stat("DIST NEXT", sprintf("%.0f", pred$distance_to_threshold %||% NA),
             sub = sprintf("current %.0f", pred$current_ovr %||% NA)),
        stat("DIST 85", sprintf("%.0f", pred$distance_to_85 %||% NA),
             sub = "diamond threshold"),
        stat("NEW RANK", if (is.finite(pred$new_rank))
          sprintf("%.0f", pred$new_rank) else "—"),
        stat("CONFIDENCE", sprintf("%.0f", pred$confidence),
             sub = toupper(pred$confidence_label)),
        stat("P(CROSS 85)", fmt_pct(pred$p_cross_85, 1)),
        stat("P(CROSS 90)", fmt_pct(pred$p_cross_90, 1)),
        stat("EXACT ΔOVR", sprintf("%+d", pred$exact_delta_ovr),
             sub = "diagnostic only"),
        stat("MOMENTUM", sprintf("%+.2f", pred$z),
             sub = pred$recent_vs_season_delta),
        stat("UPGRADE SCORE", sprintf("%.0f", pred$upgrade_score)),
        stat("THRESHOLD", if (is.finite(pred$next_threshold))
          sprintf("%.0f", pred$next_threshold) else "—")
      ),
      htmltools::tags$div(class = "flag-list",
        lapply(pred$reason_codes, function(x) pill(x, "neutral")))
    )
  })
}

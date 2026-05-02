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
    get_recent_vs_season_stats(input$ovr_name, role = role,
                               today = Sys.Date())
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
          stat("OBP 14d",  sprintf("%.3f", s$recent$obp %||% NA),
               sub = sprintf("season %.3f", s$season$obp %||% NA))
        )
      } else {
        htmltools::tags$div(class = "stat-grid stat-grid-3",
          stat("ERA 14d",  sprintf("%.2f", s$recent$era %||% NA),
               sub = sprintf("season %.2f", s$season$era %||% NA)),
          stat("WHIP 14d", sprintf("%.2f", s$recent$whip %||% NA),
               sub = sprintf("season %.2f", s$season$whip %||% NA)),
          stat("IP 14d",   sprintf("%.1f", s$recent$inningsPitched %||% NA))
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
    pred <- predict_price_change(
      stats_recent = s$recent,
      stats_season = s$season,
      role = s$role,
      current_ovr = input$ovr_current,
      rarity = input$ovr_rarity
    )
    delta_tone <- if (pred$delta_ovr > 0) "bull" else
      if (pred$delta_ovr < 0) "bear" else "neutral"
    boundary_tone <- switch(pred$boundary$risk,
                            high = "bear", medium = "warn",
                            low = "neutral")
    htmltools::tagList(
      htmltools::tags$div(class = "stat-grid stat-grid-3",
        stat("Z-SCORE", sprintf("%+.2f", pred$z),
             sub = paste(names(pred$components),
                         sprintf("%.2f", pred$components),
                         collapse = " · ")),
        stat("ΔOVR", sprintf("%+d", pred$delta_ovr), tone = delta_tone),
        stat("ΔPRICE", fmt_signed(pred$total_pct, 1), tone = delta_tone),
        stat("BOUNDARY", toupper(pred$boundary$risk), tone = boundary_tone,
             sub = if (pred$boundary$crosses)
               sprintf("jump +%.0f%%", pred$boundary$jump_pct * 100)
               else "no crossing"),
        stat("CONFIDENCE", toupper(pred$confidence)),
        stat("BASE %", fmt_signed(pred$base_pct, 1))
      )
    )
  })
}

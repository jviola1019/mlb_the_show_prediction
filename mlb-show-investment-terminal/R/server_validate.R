#' Server logic for the VALIDATE tab.
#'
#' Operates on the price history of the currently-loaded card (CARD tab).
#' No synthetic data is generated or shown.
#' @export
server_validate <- function(input, output, session, app_state) {

  val_run <- shiny::eventReactive(input$btn_run_val, {
    ph <- app_state$current_price_history()
    shiny::req(!is.null(ph), nrow(ph) >= input$val_lookback + input$val_horizon + 5)
    shinybusy::show_modal_spinner(spin = "fading-circle", color = "#10b981",
                                  text = "running walk-forward CV...")
    on.exit(shinybusy::remove_modal_spinner(), add = TRUE)
    walk_forward_cv(
      ph$price,
      horizon = input$val_horizon,
      lookback = input$val_lookback,
      n_sims_per = 400,
      boot_b = input$val_boot_b,
      ci_method = input$val_ci_method
    )
  })

  output$val_brier_violin <- plotly::renderPlotly({
    w <- val_run()
    if (is.null(w)) {
      return(plotly::plot_ly() |>
               plotly::layout(
                 paper_bgcolor = "#000000", plot_bgcolor = "#000000",
                 annotations = list(list(text = "load a card first",
                   showarrow = FALSE, font = list(color = "#52525b")))))
    }
    plotly::plot_ly(
      type = "violin",
      y = w$trades$brier_t,
      box = list(visible = TRUE),
      meanline = list(visible = TRUE),
      line = list(color = "#10b981"),
      fillcolor = "rgba(16,185,129,0.2)",
      points = "all", jitter = 0.3,
      marker = list(color = "rgba(16,185,129,0.7)", size = 5),
      name = "per-trade Brier"
    ) |>
      plotly::layout(
        paper_bgcolor = "#000000", plot_bgcolor = "#0a0a0a",
        font = list(color = "#fafafa", family = "JetBrains Mono"),
        yaxis = list(title = "Brier", gridcolor = "rgba(63,63,70,0.25)"),
        margin = list(l = 50, r = 20, t = 20, b = 50)
      ) |>
      plotly::config(displayModeBar = FALSE)
  })

  output$val_summary <- shiny::renderUI({
    w <- tryCatch(val_run(), error = function(e) NULL)
    if (is.null(w)) {
      return(htmltools::tags$div(class = "muted",
        "Click RUN VALIDATION after loading a card on the CARD tab."))
    }
    verdict <- if (!is.na(w$ic_ci[2]) && w$ic_ci[2] < 0) {
      pill("NO EDGE — CV IC<0 (sig)", "bear")
    } else if (!is.na(w$ic_point) && w$ic_point > 0.05) {
      pill("SIGNAL", "bull")
    } else if (!is.na(w$ic_point) && w$ic_point > 0) {
      pill("SOME — IC>0", "info")
    } else {
      pill("NO EDGE", "warn")
    }
    htmltools::tagList(
      verdict,
      htmltools::tags$div(class = "stat-grid stat-grid-3",
        stat("N TRADES", as.character(w$n_trades)),
        stat("BRIER", sprintf("%.3f", w$brier_point),
             sub = sprintf("[%.2f, %.2f]", w$brier_ci[1], w$brier_ci[2])),
        stat("IC", sprintf("%+.3f", w$ic_point),
             sub = sprintf("[%+.2f, %+.2f]", w$ic_ci[1], w$ic_ci[2])),
        stat("HIT RATE", fmt_pct(w$hit_rate)),
        stat("CI METHOD", toupper(w$ci_method)),
        stat("BOOT R", as.character(w$boot_b))
      )
    )
  })
}

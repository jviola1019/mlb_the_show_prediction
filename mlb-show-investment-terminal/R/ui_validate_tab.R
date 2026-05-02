#' VALIDATE tab — show walk-forward CV diagnostics on the currently-loaded
#' real card (no synthetic data).
#' @export
ui_validate_tab <- function() {
  bslib::nav_panel(
    title = "VALIDATE",
    icon = bsicons::bs_icon("check-circle"),
    htmltools::tags$div(class = "tab-panel validate-tab",

      section_header(1, "WALK-FORWARD CV (LIVE CARD)"),
      htmltools::tags$div(class = "panel muted",
        "This tab uses the price history of the card loaded on the CARD tab. ",
        "No synthetic data."),

      htmltools::tags$div(class = "panel",
        htmltools::tags$div(class = "row-2",
          shiny::sliderInput("val_horizon", "horizon (steps)",
                             min = 1, max = 14, value = 7),
          shiny::sliderInput("val_lookback", "lookback (steps)",
                             min = 8, max = 96, value = 30)
        ),
        htmltools::tags$div(class = "row-2",
          shiny::radioButtons("val_ci_method", "CI method",
                              choices = c("block-residual" = "block",
                                          "per-trade" = "per_trade"),
                              selected = "block", inline = TRUE),
          shiny::sliderInput("val_boot_b", "boot replicates",
                             min = 100, max = 2000, step = 100, value = 500)
        ),
        shiny::actionButton("btn_run_val", "RUN VALIDATION",
                            class = "btn-primary")
      ),

      section_header(2, "DISTRIBUTION OF PER-TRADE BRIER"),
      htmltools::tags$div(class = "panel",
        plotly::plotlyOutput("val_brier_violin", height = "320px")),

      section_header(3, "SUMMARY"),
      htmltools::tags$div(class = "panel",
        shiny::uiOutput("val_summary"))
    )
  )
}

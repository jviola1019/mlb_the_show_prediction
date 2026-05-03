#' MARKET SCAN tab — leaderboards of TOP BUY / TOP SELL across a discovered
#' or user-pasted UUID universe. Every card on a leaderboard has cleared all
#' six validation gates from `R/quant_validation.R`.
#' @export
ui_scan_tab <- function() {
  bslib::nav_panel(
    title = "MARKET SCAN",
    icon = bsicons::bs_icon("radar"),
    htmltools::tags$div(class = "tab-panel scan-tab",

      section_header(1, "UNIVERSE"),
      htmltools::tags$div(class = "panel",
        shiny::radioButtons("scan_mode", "mode",
          choices = c("Top Diamonds (live discovery)" = "top_diamonds",
                      "Paste UUIDs"                   = "paste_uuids",
                      "Session history (loaded cards)" = "session_history"),
          selected = "top_diamonds", inline = FALSE),
        shiny::conditionalPanel(
          condition = "input.scan_mode == 'top_diamonds'",
          shiny::sliderInput("scan_top_n", "N (cards to scan)",
                             min = 5, max = 50, value = 10, step = 5)
        ),
        shiny::conditionalPanel(
          condition = "input.scan_mode == 'paste_uuids'",
          shiny::textAreaInput("scan_uuid_paste",
            "UUIDs (one 32-hex per line)",
            value = "",
            width = "100%", rows = 6,
            placeholder = "abcdef0123456789abcdef0123456789\n...")
        )
      ),

      section_header(2, "RUN"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$div(class = "muted",
          "Rate-limited 1.5s/card to respect The Show API. ",
          "Top-10 scan takes ~20s; top-50 ~75s."),
        shiny::actionButton("btn_scan", "SCAN UNIVERSE",
                            class = "btn-primary"),
        shiny::uiOutput("scan_progress_slot")
      ),

      section_header(3, "TOP BUY (INVESTABLE only)"),
      htmltools::tags$div(class = "panel scan-buy-panel",
        reactable::reactableOutput("scan_top_buy", height = "auto")),

      section_header(4, "TOP SELL (INVESTABLE only)"),
      htmltools::tags$div(class = "panel scan-sell-panel",
        reactable::reactableOutput("scan_top_sell", height = "auto")),

      section_header(5, "OBSERVATIONAL ONLY (direction, no action)"),
      htmltools::tags$div(class = "panel",
        reactable::reactableOutput("scan_observational",
                                   height = "auto")),

      section_header(6, "DROPPED (validation gate failed)"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("scan_dropped_summary"))
    )
  )
}

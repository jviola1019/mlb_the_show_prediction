#' MARKET SCAN tab.
#' @export
ui_scan_tab <- function() {
  bslib::nav_panel(
    title = "MARKET SCAN",
    icon = bsicons::bs_icon("radar"),
    htmltools::tags$div(class = "tab-panel scan-tab",

      tab_version_banner("MARKET SCAN",
        extra = htmltools::tags$span("flip math + roster thresholds + forecast diagnostics")),
      section_header(1, "UNIVERSE"),
      htmltools::tags$div(class = "panel",
        shiny::radioButtons("scan_mode", "mode",
          choices = c("Top live rarity" = "top_live",
                      "Paste UUIDs" = "paste_uuids",
                      "Session history (loaded cards)" = "session_history"),
          selected = "top_live", inline = FALSE),
        shiny::conditionalPanel(
          condition = "input.scan_mode == 'top_live'",
          htmltools::tags$div(class = "row-2",
            shiny::selectInput("scan_rarity", "rarity",
              choices = c("Gold","Diamond","Silver","Bronze"),
              selected = "Gold"),
            shiny::sliderInput("scan_top_n", "N (cards to scan)",
                               min = 5, max = 50, value = 10, step = 5)
          )
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
          "Rate-limited 1.5s/card for The Show API. ",
          "Upgrade probabilities use MLB Stats API when player stats resolve."),
        shiny::actionButton("btn_scan", "SCAN UNIVERSE",
                            class = "btn-primary"),
        shiny::uiOutput("scan_progress_slot")
      ),

      section_header(3, "FLIP BUYS"),
      htmltools::tags$div(class = "panel scan-buy-panel",
        reactable::reactableOutput("scan_flip_buys", height = "auto")),

      section_header(4, "UPGRADE BUYS"),
      htmltools::tags$div(class = "panel scan-upgrade-panel",
        reactable::reactableOutput("scan_upgrade_buys", height = "auto")),

      section_header(5, "HOLDS"),
      htmltools::tags$div(class = "panel",
        reactable::reactableOutput("scan_holds", height = "auto")),

      section_header(6, "SELLS"),
      htmltools::tags$div(class = "panel scan-sell-panel",
        reactable::reactableOutput("scan_sells", height = "auto")),

      section_header(7, "DROPPED / INVALID"),
      htmltools::tags$div(class = "panel",
        reactable::reactableOutput("scan_dropped", height = "auto"),
        shiny::uiOutput("scan_dropped_summary"))
    )
  )
}

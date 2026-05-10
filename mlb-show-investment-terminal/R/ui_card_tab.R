#' CARD tab — search a card, ingest its listing, render forecast cone +
#' multi-horizon EV table + recommendation.
#' @export
ui_card_tab <- function() {
  bslib::nav_panel(
    title = "CARD",
    icon = bsicons::bs_icon("graph-up"),
    htmltools::tags$div(
      class = "tab-panel card-tab",

      tab_version_banner("CARD",
        extra = htmltools::tags$span("live: mlb26.theshow.com listings + listing.json")),
      htmltools::tags$div(class = "roster-slot",
                          shiny::uiOutput("card_roster_banner")),

      # 01 — FIND CARD
      section_header(1, "FIND CARD"),
      htmltools::tags$div(
        class = "panel",
        htmltools::tags$div(
          class = "row-2",
          shiny::textInput("card_search", label = "Player name",
                           value = "Mike Trout",
                           placeholder = "e.g. Bobby Witt Jr."),
          htmltools::tags$div(class = "search-actions",
                              shiny::actionButton("btn_search",
                                                  "SEARCH",
                                                  class = "btn-primary"))
        ),
        htmltools::tags$div(id = "search_results_slot",
                            shiny::uiOutput("card_search_results"))
      ),

      # 02 — INGEST listing
      section_header(2, "INGEST listing.json"),
      htmltools::tags$div(
        class = "panel",
        htmltools::tags$div(class = "row-2",
          shiny::textInput("card_uuid", "UUID (32 hex)",
                           placeholder = "abcdef0123456789abcdef0123456789"),
          htmltools::tags$div(class = "search-actions",
                              shiny::actionButton("btn_load",
                                                  "LOAD & ANALYZE",
                                                  class = "btn-primary"))
        ),
        shiny::uiOutput("card_ingest_status")
      ),

      # 03 — TARGET / recommendation
      section_header(3, "TARGET"),
      htmltools::tags$div(class = "panel target-panel",
                          shiny::uiOutput("card_target_summary")),

      # 04 — FORECAST CONE
      section_header(4, "PRICE PATH + 7-DAY FORECAST"),
      htmltools::tags$div(class = "panel",
                          shinybusy::add_busy_spinner(
                            spin = "fading-circle", color = "#10b981",
                            position = "bottom-right"),
                          plotly::plotlyOutput("card_forecast_cone",
                                               height = "420px")),

      # 05 — MULTI-HORIZON EV
      section_header(5, "MULTI-HORIZON EV"),
      htmltools::tags$div(class = "panel",
                          reactable::reactableOutput("card_ev_table")),

      # 06 — QUANT DIAGNOSTICS
      section_header(6, "QUANT DIAGNOSTICS"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("card_diagnostics")),

      # 07 — WALK-FORWARD CV + ISOTONIC
      section_header(7, "WALK-FORWARD CV + ISOTONIC"),
      htmltools::tags$div(
        class = "panel",
        htmltools::tags$div(class = "row-2 wf-controls",
          shiny::radioButtons("wf_ci_method", "CI method",
                              choices = c("Block-residual" = "block",
                                          "Per-trade (iid)" = "per_trade"),
                              selected = "block", inline = TRUE),
          shiny::sliderInput("wf_horizon", "horizon (steps)",
                             min = 1, max = 14, value = 7)
        ),
        shiny::uiOutput("card_wfcv_summary"),
        plotly::plotlyOutput("card_reliability", height = "300px")
      ),

      # 08 — Pre-commit external checks
      section_header(8, "PRE-COMMIT CHECKLIST"),
      htmltools::tags$div(
        class = "panel",
        htmltools::tags$ul(class = "external-links",
          htmltools::tags$li(htmltools::tags$a(href = "https://showzone.com",
                                               target = "_blank",
                                               "ShowZone (price tracker)")),
          htmltools::tags$li(htmltools::tags$a(href = "https://showdd.io",
                                               target = "_blank",
                                               "ShowDD (DB)")),
          htmltools::tags$li(htmltools::tags$a(href = "https://www.baseball-reference.com",
                                               target = "_blank",
                                               "Baseball Reference"))
        )
      ),

      # Optional LLM cross-check
      shiny::uiOutput("card_anthropic_block")
    )
  )
}

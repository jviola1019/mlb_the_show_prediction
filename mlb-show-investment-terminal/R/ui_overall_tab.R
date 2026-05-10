#' OVERALL dashboard tab — landing page showing app health, last-scan
#' partition counts, tier distribution, and live API freshness.
#' @export
ui_overall_tab <- function() {
  bslib::nav_panel(
    title = "OVERALL",
    icon = bsicons::bs_icon("speedometer2"),
    htmltools::tags$div(class = "tab-panel overall-tab",

      tab_version_banner("OVERALL",
        extra = htmltools::tags$span("dashboard; reads app_state only")),
      htmltools::tags$div(class = "roster-slot",
                          shiny::uiOutput("overall_roster_banner")),

      section_header(1, "APP HEALTH"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$div(class = "dashboard-status-row",
                            shiny::uiOutput("overall_status_badge")),
        shiny::uiOutput("overall_health_grid")
      ),

      section_header(2, "LAST SCAN"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("overall_scan_summary")),

      section_header(3, "TIER DISTRIBUTION"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("overall_tier_bar")),

      section_header(4, "MARKET HEALTH (last scan)"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("overall_market_health")),

      htmltools::tags$div(class = "muted",
        htmltools::HTML(paste(
          "OVERALL is a live-state dashboard. Validation gates are",
          "applied per card on the CARD and MARKET SCAN tabs; this view",
          "only summarises their results. No action verbs are published",
          "here."
        )))
    )
  )
}

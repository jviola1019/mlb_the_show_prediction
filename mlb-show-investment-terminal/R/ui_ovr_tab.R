#' OVR PRED tab — predict ΔOVR and ΔPrice% from real MLB stats deltas.
#' @export
ui_ovr_tab <- function() {
  bslib::nav_panel(
    title = "OVR PRED",
    icon = bsicons::bs_icon("activity"),
    htmltools::tags$div(class = "tab-panel ovr-tab",

      htmltools::tags$div(class = "roster-slot",
                          shiny::uiOutput("ovr_roster_banner")),

      section_header(1, "PLAYER LOOKUP"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$div(class = "row-2",
          shiny::textInput("ovr_name", "Player name", value = "Mike Trout"),
          htmltools::tags$div(class = "search-actions",
            shiny::actionButton("btn_ovr_load", "FETCH STATS",
                                class = "btn-primary"))
        ),
        htmltools::tags$div(class = "row-3 ovr-controls",
          shiny::selectInput("ovr_role", "role",
            choices = c("auto" = "auto", "hitter" = "hitter",
                        "pitcher" = "pitcher"),
            selected = "auto"),
          shiny::numericInput("ovr_current", "current OVR", 80, 50, 99),
          shiny::selectInput("ovr_rarity", "rarity",
            choices = c("Diamond","Gold","Silver","Bronze"),
            selected = "Gold")
        )
      ),

      section_header(2, "RECENT vs SEASON"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("ovr_stats_summary")),

      section_header(3, "PREDICTION"),
      htmltools::tags$div(class = "panel",
                          shiny::uiOutput("ovr_prediction"))
    )
  )
}

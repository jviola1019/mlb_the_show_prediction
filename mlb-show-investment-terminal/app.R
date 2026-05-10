# MLB The Show 26 Investment Terminal --- entry point.
#
# Source pattern: shinyapps.io and rocker/shiny boot from this single file.
# We `source()` every R/*.R rather than installing the package so the same
# entry point works locally (`shiny::runApp(".")`) and on shinyapps.io.

library(shiny)

R_DIR <- file.path(getwd(), "R")
if (!dir.exists(R_DIR)) {
  R_DIR <- file.path(dirname(sys.frame(1)$ofile %||% "."), "R")
}
for (f in list.files(R_DIR, pattern = "\\.R$", full.names = TRUE)) {
  source(f, local = FALSE)
}

# Load roster updates once at boot
.roster_updates <- tryCatch(
  readRDS(file.path("data", "roster_updates.rds")),
  error = function(e) NULL
)

# Theme: bslib v5 + futuristic emerald-on-black + JetBrains Mono everywhere.
theme <- bslib::bs_theme(
  preset = "shiny",
  primary = "#10b981",
  bg = "#000000", fg = "#fafafa",
  base_font = bslib::font_collection(
    bslib::font_google("JetBrains Mono", local = FALSE),
    "ui-monospace", "SF Mono", "Menlo", "monospace"
  )
)

ui <- bslib::page_navbar(
  title = htmltools::tags$div(class = "app-title",
    htmltools::tags$span(class = "title-glyph", "◢◤"),
    htmltools::tags$span("MLB · INVESTMENT TERMINAL"),
    htmltools::tags$span(class = "title-version", "v1.0")
  ),
  theme = theme,
  navbar_options = bslib::navbar_options(bg = "#000000",
                                         underline = FALSE,
                                         collapsible = TRUE),
  header = htmltools::tagList(
    htmltools::tags$head(
      htmltools::tags$meta(name = "viewport",
        content = "width=device-width, initial-scale=1, maximum-scale=1"),
      htmltools::tags$link(rel = "icon", type = "image/svg+xml",
                           href = "favicon.svg"),
      htmltools::tags$link(rel = "alternate icon", href = "favicon.ico"),
      htmltools::tags$link(rel = "stylesheet", href = "theme.css"),
      htmltools::tags$script(src = "particles.js", defer = NA),
      htmltools::tags$script(src = "tab_transitions.js", defer = NA),
      htmltools::tags$script(src = "viewport.js", defer = NA)
    ),
    htmltools::tags$div(class = "scanline-overlay"),
    loading_screen()
  ),
  ui_overall_tab(),
  ui_card_tab(),
  ui_ovr_tab(),
  ui_scan_tab(),
  ui_validate_tab(),
  ui_method_tab()
)

server <- function(input, output, session) {
  loaded_uuids_rv <- shiny::reactiveVal(character(0))
  api_log <- shiny::reactiveValues(
    theshow_ok = numeric(0),  theshow_err = numeric(0),
    mlb_ok = numeric(0),      mlb_err = numeric(0)
  )
  app_state <- shiny::reactiveValues(
    roster_updates = .roster_updates,
    current_listing = NULL,
    current_price_history = function() NULL,
    loaded_uuids = loaded_uuids_rv,
    api_log = api_log,
    last_scan_df = NULL,
    last_scan_at = NULL,
    last_card_listing_at = NULL
  )

  # Track every UUID the user loads so SESSION HISTORY scan mode has data.
  shiny::observeEvent(input$card_uuid, {
    u <- input$card_uuid
    if (is_valid_uuid(u)) {
      cur <- loaded_uuids_rv()
      if (!u %in% cur) loaded_uuids_rv(c(cur, u))
    }
  }, ignoreInit = TRUE)

  # CARD tab
  server_card(input, output, session, app_state)

  # Wire CARD listing -> app_state for VALIDATE tab consumption
  shiny::observe({
    L <- tryCatch(input$card_uuid, error = function(e) NULL)
    # NOTE: server_card holds the reactive; we expose the price history via
    # an input shim. Here we simply re-derive on demand from the cached
    # listing via get_listing(uuid) (memoised, so no extra network).
    app_state$current_price_history <- function() {
      if (is_valid_uuid(input$card_uuid %||% "")) {
        L2 <- get_listing(input$card_uuid)
        if (is.null(L2$error)) extract_price_history(L2) else NULL
      } else NULL
    }
  })

  server_ovr(input, output, session, app_state)
  server_validate(input, output, session, app_state)
  server_scan(input, output, session, app_state)
  server_overall(input, output, session, app_state)

  # Hide bootscreen ~600ms after first session render
  session$onFlushed(function() {
    shinyjs_message <- "document.getElementById('bootscreen')?.classList.add('done');"
    session$sendCustomMessage("hideBootscreen", list(after_ms = 600))
  }, once = TRUE)
}

shinyApp(ui, server)

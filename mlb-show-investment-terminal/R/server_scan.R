#' Server logic for the MARKET SCAN tab.
#' @export
server_scan <- function(input, output, session, app_state) {

  scan_run <- shiny::eventReactive(input$btn_scan, {
    mode <- input$scan_mode
    uuids <- character(0)
    if (mode == "top_diamonds") {
      n_req <- as.integer(input$scan_top_n %||% 10L)
      td <- tryCatch(discover_top_listings("Diamond",
                                            max_per_page = n_req),
                     error = function(e) {
                       shiny::showNotification(
                         paste("discover failed:", conditionMessage(e)),
                         type = "error", duration = 6)
                       NULL
                     })
      uuids <- if (is.null(td)) character(0) else td$uuid
    } else if (mode == "paste_uuids") {
      raw <- input$scan_uuid_paste %||% ""
      uuids <- trimws(strsplit(raw, "\n", fixed = TRUE)[[1]])
      uuids <- uuids[nchar(uuids) > 0L]
    } else if (mode == "session_history") {
      uuids <- app_state$loaded_uuids() %||% character(0)
    }
    if (length(uuids) == 0L) {
      shiny::showNotification("No UUIDs to scan.", type = "warning",
                              duration = 4)
      return(NULL)
    }
    n <- length(uuids)
    p <- shiny::Progress$new(session, min = 0, max = n)
    on.exit(p$close(), add = TRUE)
    p$set(value = 0,
          message = sprintf("scanning %d cards", n),
          detail  = "starting...")
    progress_cb <- function(i, n_total, name) {
      p$set(value = i,
            message = sprintf("scanning %d of %d", i, n_total),
            detail  = name)
    }
    scan_universe(uuids, horizon = 7L, rate_delay = 1.5,
                  progress = progress_cb)
  })

  scan_parts <- shiny::reactive({
    df <- scan_run()
    if (is.null(df)) return(NULL)
    scan_partition(df)
  })

  render_table <- function(df, kind = c("buy","sell","observe")) {
    kind <- match.arg(kind)
    if (is.null(df) || nrow(df) == 0L) {
      return(reactable::reactable(
        data.frame(empty = "no rows"), pagination = FALSE, sortable = FALSE,
        theme = .scan_reactable_theme()
      ))
    }
    cols <- list(
      name = reactable::colDef(name = "PLAYER", minWidth = 130),
      rarity = reactable::colDef(name = "RARITY", maxWidth = 90),
      ovr = reactable::colDef(name = "OVR", maxWidth = 60, align = "right"),
      ask = reactable::colDef(name = "ASK", align = "right",
        format = reactable::colFormat(separators = TRUE, digits = 0)),
      ev_7d = reactable::colDef(name = "E[ret]", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 2)),
      score = reactable::colDef(name = "SCORE", align = "right"),
      action = reactable::colDef(name = "ACTION", align = "left",
                                 maxWidth = 120),
      direction = reactable::colDef(name = "DIR", maxWidth = 50,
                                    align = "center"),
      ic_point = reactable::colDef(name = "CV IC", align = "right",
        format = reactable::colFormat(digits = 3)),
      gates_failed_csv = reactable::colDef(name = "FAILED GATES",
                                            minWidth = 160)
    )
    show_cols <- if (kind == "observe") {
      c("name","rarity","ovr","ask","direction","ic_point",
        "gates_failed_csv")
    } else {
      c("name","rarity","ovr","ask","ev_7d","score","action","ic_point")
    }
    df <- df[, show_cols, drop = FALSE]
    cols <- cols[names(cols) %in% show_cols]
    reactable::reactable(
      df, columns = cols, defaultColDef = reactable::colDef(
        headerClass = "rt-header"),
      compact = TRUE, bordered = TRUE, pagination = FALSE,
      sortable = TRUE, theme = .scan_reactable_theme(),
      onClick = reactable::JS(
        "function(rowInfo) {",
        "  if (!rowInfo) return;",
        "  var uuid = rowInfo.row.uuid;",
        "  if (uuid) {",
        "    Shiny.setInputValue('card_uuid', uuid, {priority:'event'});",
        "    var t = document.querySelector('a.nav-link[data-bs-toggle][href*=\"CARD\"]');",
        "    if (t) t.click();",
        "  }",
        "}")
    )
  }

  output$scan_top_buy <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$buy, "buy")
  })
  output$scan_top_sell <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$sell, "sell")
  })
  output$scan_observational <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$observe, "observe")
  })

  output$scan_dropped_summary <- shiny::renderUI({
    p <- scan_parts()
    if (is.null(p)) return(htmltools::tags$div(class = "muted",
                            "no scan run yet"))
    if (nrow(p$dropped) == 0L) {
      return(htmltools::tags$div(class = "muted",
                                 "no dropped cards in this scan"))
    }
    reasons <- table(p$dropped$gates_failed_csv)
    htmltools::tagList(
      htmltools::tags$div(class = "muted",
        sprintf("%d cards dropped:", nrow(p$dropped))),
      htmltools::tags$ul(
        lapply(names(reasons), function(r) {
          htmltools::tags$li(sprintf("%s — %d card(s)", r, reasons[[r]]))
        })
      )
    )
  })
}

.scan_reactable_theme <- function() {
  reactable::reactableTheme(
    backgroundColor = "#0a0a0a",
    borderColor = "rgba(63,63,70,0.6)",
    color = "#fafafa",
    cellPadding = "6px 10px",
    headerStyle = list(color = "#10b981",
                       letterSpacing = "0.15em",
                       fontSize = "10px",
                       textTransform = "uppercase")
  )
}

#' Server logic for the MARKET SCAN tab.
#' @export
server_scan <- function(input, output, session, app_state) {

  scan_run <- shiny::eventReactive(input$btn_scan, {
    mode <- input$scan_mode
    uuids <- character(0)
    if (mode == "top_live") {
      n_req <- as.integer(input$scan_top_n %||% 10L)
      rarity <- input$scan_rarity %||% "Gold"
      td <- tryCatch(discover_top_listings(rarity, max_per_page = n_req),
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
    df <- scan_universe(uuids, horizon = 7L, rate_delay = 1.5,
                        progress = progress_cb,
                        include_upgrade_stats = TRUE)
    app_state$last_scan_df <- df
    app_state$last_scan_at <- Sys.time()
    df
  })

  scan_parts <- shiny::reactive({
    df <- scan_run()
    if (is.null(df)) return(NULL)
    scan_partition(df)
  })

  render_table <- function(df, kind = c("flip","upgrade","holds","sell","dropped")) {
    kind <- match.arg(kind)
    if (is.null(df) || nrow(df) == 0L) {
      return(reactable::reactable(
        data.frame(empty = "no rows"), pagination = FALSE, sortable = FALSE,
        theme = .scan_reactable_theme()
      ))
    }
    cols <- list(
      uuid = reactable::colDef(show = FALSE),
      name = reactable::colDef(name = "PLAYER", minWidth = 130),
      rarity = reactable::colDef(name = "RARITY", maxWidth = 90),
      ovr = reactable::colDef(name = "OVR", maxWidth = 60, align = "right"),
      raw_bid = reactable::colDef(name = "RAW BID", align = "right",
        format = reactable::colFormat(separators = TRUE, digits = 0)),
      raw_ask = reactable::colDef(name = "RAW ASK", align = "right",
        format = reactable::colFormat(separators = TRUE, digits = 0)),
      after_tax_sale = reactable::colDef(name = "AFTER TAX", align = "right",
        format = reactable::colFormat(separators = TRUE, digits = 1)),
      flip_profit = reactable::colDef(name = "PROFIT", align = "right",
        format = reactable::colFormat(separators = TRUE, digits = 1)),
      flip_roi = reactable::colDef(name = "ROI", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 2)),
      spread_pct = reactable::colDef(name = "SPREAD", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 1)),
      liquidity_recent = reactable::colDef(name = "LIQ 24H", align = "right"),
      flip_action = reactable::colDef(name = "FLIP", maxWidth = 100),
      flip_reason_codes = reactable::colDef(name = "FLIP REASONS",
                                            minWidth = 220),
      forecast_direction = reactable::colDef(name = "FORECAST",
                                             minWidth = 130),
      forecast_ev_7d = reactable::colDef(name = "FORECAST EV", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 2)),
      new_rank = reactable::colDef(name = "NEW RANK", align = "right"),
      next_threshold = reactable::colDef(name = "NEXT", align = "right"),
      distance_to_threshold = reactable::colDef(name = "DIST", align = "right"),
      distance_to_85 = reactable::colDef(name = "DIST 85", align = "right"),
      distance_to_90 = reactable::colDef(name = "DIST 90", align = "right"),
      p_upgrade = reactable::colDef(name = "P(UP)", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 1)),
      p_downgrade = reactable::colDef(name = "P(DOWN)", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 1)),
      p_cross_next_threshold = reactable::colDef(name = "P(CROSS)", align = "right",
        format = reactable::colFormat(percent = TRUE, digits = 1)),
      upgrade_confidence = reactable::colDef(name = "CONF", align = "right",
        format = reactable::colFormat(digits = 0)),
      upgrade_score = reactable::colDef(name = "UPG SCORE", align = "right",
        format = reactable::colFormat(digits = 0)),
      upgrade_action = reactable::colDef(name = "UPGRADE", minWidth = 130),
      upgrade_reason_codes = reactable::colDef(name = "UPGRADE REASONS",
                                               minWidth = 230),
      scan_status = reactable::colDef(name = "STATUS"),
      gates_failed_csv = reactable::colDef(name = "FORECAST GATES",
                                           minWidth = 180)
    )
    show_cols <- switch(kind,
      flip = c("uuid","name","rarity","ovr","raw_bid","raw_ask",
               "after_tax_sale","flip_profit","flip_roi","spread_pct",
               "liquidity_recent","forecast_direction","flip_reason_codes"),
      upgrade = c("uuid","name","rarity","ovr","new_rank","next_threshold",
                  "distance_to_threshold","distance_to_85",
                  "p_cross_next_threshold",
                  "p_upgrade","p_downgrade","upgrade_confidence",
                  "upgrade_score","upgrade_action","upgrade_reason_codes"),
      holds = c("uuid","name","rarity","ovr","flip_action","upgrade_action",
                "forecast_direction","forecast_ev_7d","flip_roi",
                "distance_to_85","p_cross_next_threshold","flip_reason_codes",
                "upgrade_reason_codes"),
      sell = c("uuid","name","rarity","ovr","flip_action","upgrade_action",
               "flip_roi","p_downgrade","forecast_direction",
               "flip_reason_codes","upgrade_reason_codes"),
      dropped = c("uuid","name","rarity","ovr","raw_bid","raw_ask",
                  "scan_status","flip_reason_codes","upgrade_reason_codes",
                  "gates_failed_csv")
    )
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

  output$scan_flip_buys <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$flip_buy, "flip")
  })
  output$scan_upgrade_buys <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$upgrade_buy, "upgrade")
  })
  output$scan_holds <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$holds, "holds")
  })
  output$scan_sells <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$sell, "sell")
  })
  output$scan_dropped <- reactable::renderReactable({
    p <- scan_parts(); shiny::req(p); render_table(p$dropped, "dropped")
  })

  output$scan_dropped_summary <- shiny::renderUI({
    p <- scan_parts()
    if (is.null(p)) return(htmltools::tags$div(class = "muted",
                            "no scan run yet"))
    if (nrow(p$dropped) == 0L) {
      return(htmltools::tags$div(class = "muted",
                                 "no dropped or invalid cards in this scan"))
    }
    reasons <- table(p$dropped$flip_reason_codes)
    htmltools::tagList(
      htmltools::tags$div(class = "muted",
        sprintf("%d cards dropped / invalid:", nrow(p$dropped))),
      htmltools::tags$ul(
        lapply(names(reasons), function(r) {
          htmltools::tags$li(sprintf("%s - %d card(s)", r, reasons[[r]]))
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
    headerStyle = list(color = "#a1a1aa",
                       letterSpacing = "0.15em",
                       fontSize = "10px",
                       textTransform = "uppercase")
  )
}

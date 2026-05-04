#' Server logic for the CARD tab.
#' @export
server_card <- function(input, output, session, app_state) {

  # Roster banner --------------------------------------------------------------
  output$card_roster_banner <- shiny::renderUI({
    roster_banner(today = Sys.Date(), updates = app_state$roster_updates)
  })

  # Search ---------------------------------------------------------------------
  search_res <- shiny::eventReactive(input$btn_search, {
    shiny::req(nchar(input$card_search) > 0)
    shinybusy::show_modal_spinner(spin = "atom", color = "#10b981",
                                  text = "querying The Show...")
    on.exit(shinybusy::remove_modal_spinner(), add = TRUE)
    search_card(input$card_search)
  })

  output$card_search_results <- shiny::renderUI({
    res <- search_res()
    shiny::req(res)
    if (length(res$listings) == 0L) {
      return(htmltools::tags$div(class = "muted",
        sprintf("no listings (year=%s) — try a different name",
                as.character(res$year %||% NA))))
    }
    rows <- lapply(seq_along(res$listings), function(i) {
      L <- res$listings[[i]]
      uuid <- L$item$uuid %||% "?"
      htmltools::tags$div(
        class = "search-row",
        onclick = sprintf("Shiny.setInputValue('card_uuid', '%s', {priority:'event'});", uuid),
        htmltools::tags$span(class = "sr-name", L$item$name %||% L$listing_name),
        pill(L$item$rarity %||% "?", rarity_pill_tone(L$item$rarity)),
        htmltools::tags$span(class = "sr-ovr", paste0("OVR ", L$item$ovr %||% "?")),
        htmltools::tags$span(class = "sr-team", L$item$team %||% ""),
        htmltools::tags$span(class = "sr-ask",
                             sprintf("ASK %s",
                                     fmt_stubs(L$best_sell_price %||% NA)))
      )
    })
    htmltools::tagList(
      htmltools::tags$div(class = "muted",
                          sprintf("year=%s · %d listings (tap to load)",
                                  as.character(res$year), length(res$listings))),
      rows
    )
  })

  # Ingest ---------------------------------------------------------------------
  listing <- shiny::eventReactive(input$btn_load, {
    shiny::req(is_valid_uuid(input$card_uuid))
    shinybusy::show_modal_spinner(spin = "fading-circle", color = "#10b981",
                                  text = "fetching listing.json...")
    on.exit(shinybusy::remove_modal_spinner(), add = TRUE)
    get_listing(input$card_uuid)
  }, ignoreInit = TRUE)

  # Auto-load when search row is clicked + UUID populated
  shiny::observeEvent(input$card_uuid, {
    if (is_valid_uuid(input$card_uuid)) {
      shiny::isolate({
        shiny::updateActionButton(session, "btn_load")
      })
    }
  }, ignoreInit = TRUE)

  output$card_ingest_status <- shiny::renderUI({
    L <- listing()
    if (is.null(L) || !is.null(L$error)) {
      return(htmltools::tags$div(class = "muted",
        if (!is.null(L$error)) paste("error:", L$error) else "no listing"))
    }
    item <- L$item %||% list()
    htmltools::tags$div(class = "ingest-status",
      htmltools::tags$span(class = "sr-name", item$name %||% "?"),
      pill(item$rarity %||% "?", rarity_pill_tone(item$rarity)),
      htmltools::tags$span(class = "sr-ovr", paste0("OVR ", item$ovr %||% "?")),
      htmltools::tags$span(class = "sr-team", item$team %||% "?"),
      htmltools::tags$span(class = "muted",
                           sprintf("ph rows: %d",
                                   nrow(extract_price_history(L))))
    )
  })

  # Forecast pipeline ----------------------------------------------------------
  price_history <- shiny::reactive({
    L <- listing()
    shiny::req(L)
    extract_price_history(L)
  })

  rets <- shiny::reactive({
    ph <- price_history()
    shiny::req(nrow(ph) >= 8)
    log_returns(ph$price)
  })

  forecast <- shiny::reactive({
    r <- rets()
    L <- listing()
    shiny::req(length(r) >= 8, L$best_sell_price)
    block_bootstrap(r, current = L$best_sell_price,
                    horizon = input$wf_horizon, n_sims = 1500)
  })

  ev_horizons <- shiny::reactive({
    L <- listing()
    r <- rets()
    shiny::req(length(r) >= 8, L$best_sell_price)
    out <- lapply(c(1, 3, 7), function(h) {
      fc <- block_bootstrap(r, L$best_sell_price, h, n_sims = 1000)
      ev <- compute_ev(L$best_sell_price, L$best_buy_price %||% 0, fc, h)
      data.frame(
        horizon = sprintf("%dd", h),
        e_ret = ev$expected_ret,
        p_win = ev$p_profit,
        p5  = ev$p5_ret,
        p95 = ev$p95_ret,
        kelly_half = ev$kelly_half,
        breakeven = ev$breakeven
      )
    })
    do.call(rbind, out)
  })

  diagnostics <- shiny::reactive({
    ph <- price_history()
    r  <- rets()
    shiny::req(length(r) >= 8)
    fit <- linear_reg_hac(ph$price)
    h <- hurst_exponent(r)
    last30 <- utils::tail(ph$price, 30)
    z30 <- if (length(last30) >= 5L && stats::sd(last30) > 0) {
      (utils::tail(ph$price, 1) - mean(last30)) / stats::sd(last30)
    } else NA_real_
    vol_ann <- stats::sd(r) * sqrt(365)
    list(
      slope = fit$slope, p_hac = fit$p_hac, t_hac = fit$t_hac,
      hurst = h, z30 = z30, vol_ann = vol_ann,
      n = length(ph$price), spread_pct = {
        L <- listing()
        if (!is.null(L$best_sell_price) && !is.null(L$best_buy_price) &&
            L$best_sell_price > 0) {
          (L$best_sell_price - L$best_buy_price) / L$best_sell_price
        } else NA_real_
      }
    )
  })

  wfcv <- shiny::reactive({
    ph <- price_history()
    shiny::req(nrow(ph) >= input$wf_horizon * 6)
    walk_forward_cv(ph$price, horizon = input$wf_horizon,
                    lookback = max(20, input$wf_horizon * 4),
                    n_sims_per = 400, boot_b = 400,
                    ci_method = input$wf_ci_method)
  })

  # Probe whether isotonic calibration actually IMPROVES Brier on a
  # held-out half of the walk-forward trades. Stronger than the previous
  # "did isotonic run without error?" check — calibration that produces a
  # finite vector but degrades Brier is treated as a failed gate.
  calibration_check <- shiny::reactive({
    w <- tryCatch(wfcv(), error = function(e) NULL)
    if (is.null(w) || nrow(w$trades) < 30L) {
      return(list(ok = FALSE,
                  reason = sprintf("only %s trades (need >= 30 for held-out)",
                                   if (is.null(w)) "0" else
                                     as.character(nrow(w$trades))),
                  brier_pre = NA_real_, brier_post = NA_real_,
                  delta = NA_real_, n_train = 0L, n_test = 0L))
    }
    calibration_held_out_check(w$trades$p_up, w$trades$realized_up,
                               min_n = 30L)
  })

  calibration_ok <- shiny::reactive({ isTRUE(calibration_check()$ok) })

  gates <- shiny::reactive({
    L <- listing()
    ph <- price_history()
    w <- tryCatch(wfcv(), error = function(e) NULL)
    validation_gates(price_history = ph, listing = L, wfcv = w,
                     horizon = input$wf_horizon,
                     calibration_ok = calibration_check())
  })

  verdict <- shiny::reactive({ gating_verdict(gates()) })

  # H8: broadcast verdict status to body[data-verdict] so theme.css can
  # paint the blocked / observational-only visual state. Idempotent.
  shiny::observe({
    v <- verdict()
    session$sendCustomMessage("setVerdict", list(status = v$status))
  })

  recommendation <- shiny::reactive({
    L <- listing()
    e <- ev_horizons()
    d <- diagnostics()
    w <- tryCatch(wfcv(), error = function(e) NULL)
    v <- verdict()

    # H5: BUY/SELL labels are only ever emitted when the verdict is
    # INVESTABLE. Anything else returns a governance-safe stub before
    # `recommendation_score()` is even called.
    if (v$status == "NOT INVESTABLE") {
      return(list(score = NA_integer_, action = "ABSTAIN",
                  flags = list(), verdict = v))
    }
    ev7 <- e[e$horizon == "7d", "e_ret"]
    base <- recommendation_score(
      ev = ev7, drift_p = d$p_hac,
      drift_slope = d$slope, z30 = d$z30,
      hurst = d$hurst, spread_pct = d$spread_pct,
      cv_ic_point = w$ic_point %||% NA_real_,
      cv_ic_upper = if (length(w$ic_ci %||% NULL) == 2L) w$ic_ci[2]
                    else NA_real_
    )
    if (v$status == "OBSERVATIONAL ONLY") {
      # H5: Strip BUY/SELL/HOLD verb. Keep only direction.
      direction <- if (is.na(base$score)) "OBSERVE" else
        if (base$score > 0) "OBSERVE ▲" else
        if (base$score < 0) "OBSERVE ▼" else "OBSERVE"
      base$action <- direction
      # Strip Kelly-suggesting flags so the user can't be misled even
      # by the flag list. Drop +EV / -EV magnitude flags entirely.
      base$flags <- Filter(function(f) {
        !grepl("^[+-]EV", f$text %||% "", perl = TRUE)
      }, base$flags %||% list())
    }
    base$verdict <- v
    base
  })

  # Render: target / recommendation -------------------------------------------
  output$card_target_summary <- shiny::renderUI({
    L <- listing()
    rec <- recommendation()
    g <- gates()
    v <- verdict()
    if (is.null(L)) {
      return(htmltools::tags$div(class = "muted",
                                 "load a card to see the verdict"))
    }
    item <- L$item %||% list()
    liq <- liquidity_score(L$completed_orders %||% list())
    score_text <- if (is.na(rec$score)) "score — (gated)" else
      sprintf("score %+d", rec$score)
    verdict_pill <- pill(v$status, v$badge_tone)
    reasons_block <- if (length(v$reasons) > 0L) {
      htmltools::tags$div(class = "verdict-reasons",
        htmltools::tags$div(class = "verdict-headline", v$headline),
        htmltools::tags$ul(class = "verdict-reason-list",
          lapply(v$reasons, function(r) htmltools::tags$li(r))))
    } else NULL

    htmltools::tagList(
      htmltools::tags$div(class = "target-head",
        htmltools::tags$div(class = "target-name", item$name %||% "?"),
        pill(item$rarity %||% "?", rarity_pill_tone(item$rarity)),
        htmltools::tags$span(class = "target-ovr",
                             paste0("OVR ", item$ovr %||% "?")),
        htmltools::tags$span(class = "target-team", item$team %||% ""),
        verdict_pill
      ),
      htmltools::tags$div(class = "target-signal-row",
        signal_pill(rec$action),
        htmltools::tags$div(class = "score-density",
          htmltools::tags$div(class = "score", score_text),
          density_dots(liq$score)
        )
      ),
      reasons_block,
      flag_list(rec$flags),
      htmltools::tags$div(class = "stat-grid",
        stat("ASK", fmt_stubs(L$best_sell_price)),
        stat("BID", fmt_stubs(L$best_buy_price)),
        stat("SPREAD", fmt_pct(diagnostics()$spread_pct))
      ),
      htmltools::tags$div(class = "section-header data-quality-header",
        htmltools::tags$span(class = "section-num", "DQ"),
        htmltools::tags$span(class = "section-title", "DATA QUALITY")),
      gates_summary_pills(g)
    )
  })

  # Forecast cone --------------------------------------------------------------
  # H1: do not render an actionable cone when the verdict is NOT INVESTABLE.
  # OBSERVATIONAL ONLY may render history + cone but with a watermark
  # ("FORECAST UNCERTAIN — gates 5/6 failed") and rose-tinted bands so the
  # visual cannot be mistaken for a tradable signal.
  output$card_forecast_cone <- plotly::renderPlotly({
    fc <- forecast()
    shiny::req(fc)
    v <- verdict()
    s <- fc$summary
    ph <- price_history()

    if (v$status == "NOT INVESTABLE") {
      return(plotly::plot_ly() |>
        plotly::layout(
          paper_bgcolor = "#000000", plot_bgcolor = "#0a0a0a",
          xaxis = list(visible = FALSE), yaxis = list(visible = FALSE),
          annotations = list(list(
            text = paste("FORECAST BLOCKED — ABSTAIN",
                         "<br><span style='font-size:11px;color:#a1a1aa'>",
                         "validation gates failed; no actionable cone",
                         "</span>"),
            showarrow = FALSE, xref = "paper", yref = "paper",
            x = 0.5, y = 0.5, align = "center",
            font = list(color = "#fda4af", family = "JetBrains Mono",
                        size = 18)
          ))
        ) |>
        plotly::config(displayModeBar = FALSE))
    }

    hist_x <- as.numeric(ph$timestamp) - max(as.numeric(ph$timestamp))
    hist_x <- hist_x / 3600  # hours back
    fc_x <- seq(0, by = 24, length.out = nrow(s))  # forecast in hours fwd

    is_obs <- v$status == "OBSERVATIONAL ONLY"
    band_color <- if (is_obs) "rgba(251,191,36,%s)" else
                              "rgba(16,185,129,%s)"
    line_color <- if (is_obs) "#fbbf24" else "#10b981"

    p <- plotly::plot_ly() |>
      plotly::add_lines(x = hist_x, y = ph$price,
                        line = list(color = line_color, width = 2),
                        name = "history") |>
      plotly::add_ribbons(x = fc_x, ymin = s$p5, ymax = s$p95,
                          fillcolor = sprintf(band_color, "0.10"),
                          line = list(color = "transparent"),
                          name = "5-95%") |>
      plotly::add_ribbons(x = fc_x, ymin = s$p25, ymax = s$p75,
                          fillcolor = sprintf(band_color, "0.20"),
                          line = list(color = "transparent"),
                          name = "25-75%") |>
      plotly::add_lines(x = fc_x, y = s$p50,
                        line = list(color = line_color, width = 2,
                                    dash = "dash"),
                        name = "median") |>
      plotly::layout(
        paper_bgcolor = "#000000",
        plot_bgcolor  = "#0a0a0a",
        font = list(color = "#fafafa", family = "JetBrains Mono"),
        xaxis = list(title = "hours (history ←  →  forecast)",
                     gridcolor = "rgba(63,63,70,0.25)",
                     zerolinecolor = "rgba(16,185,129,0.4)"),
        yaxis = list(title = "stubs",
                     gridcolor = "rgba(63,63,70,0.25)"),
        showlegend = TRUE,
        legend = list(font = list(color = "#fafafa")),
        margin = list(l = 50, r = 20, t = 40, b = 50),
        annotations = if (is_obs) list(list(
          text = "OBSERVATIONAL ONLY — not a tradable forecast",
          showarrow = FALSE, xref = "paper", yref = "paper",
          x = 0.5, y = 1.06, xanchor = "center",
          font = list(color = "#fcd34d", size = 11,
                      family = "JetBrains Mono")
        )) else NULL
      ) |>
      plotly::config(displayModeBar = FALSE)
    p
  })

  # EV table -------------------------------------------------------------------
  # H2: blank ALL actionable EV columns whenever verdict != INVESTABLE.
  # Kelly especially must never appear under a soft-gate failure (it implies
  # a real stake size). Only INVESTABLE shows full numbers.
  output$card_ev_table <- reactable::renderReactable({
    e <- ev_horizons()
    v <- verdict()
    if (v$status != "INVESTABLE") {
      # Blank actionable numbers — show structure + horizon labels only.
      e[, c("e_ret","p_win","p5","p95","kelly_half","breakeven")] <- NA_real_
    }
    reactable::reactable(
      e,
      defaultColDef = reactable::colDef(
        headerClass = "rt-header",
        align = "right"
      ),
      columns = list(
        horizon = reactable::colDef(name = "HORIZON", align = "left",
                                    minWidth = 80),
        e_ret = reactable::colDef(name = "E[ret]", format =
          reactable::colFormat(percent = TRUE, digits = 2)),
        p_win = reactable::colDef(name = "P(win)", format =
          reactable::colFormat(percent = TRUE, digits = 1)),
        p5    = reactable::colDef(name = "P5",    format =
          reactable::colFormat(percent = TRUE, digits = 1)),
        p95   = reactable::colDef(name = "P95",   format =
          reactable::colFormat(percent = TRUE, digits = 1)),
        kelly_half = reactable::colDef(name = "½Kelly", format =
          reactable::colFormat(percent = TRUE, digits = 2)),
        breakeven = reactable::colDef(name = "BREAKEVEN", format =
          reactable::colFormat(separators = TRUE, digits = 0))
      ),
      compact = TRUE, bordered = TRUE, striped = FALSE,
      theme = reactable::reactableTheme(
        backgroundColor = "#0a0a0a",
        borderColor = "rgba(63,63,70,0.6)",
        color = "#fafafa",
        cellPadding = "6px 10px",
        headerStyle = list(color = "#10b981",
                           letterSpacing = "0.15em",
                           fontSize = "10px",
                           textTransform = "uppercase")
      )
    )
  })

  # Diagnostics ----------------------------------------------------------------
  output$card_diagnostics <- shiny::renderUI({
    d <- diagnostics()
    shiny::req(d)
    htmltools::tags$div(class = "stat-grid stat-grid-3",
      stat("Z(30)", sprintf("%+.2f", d$z30)),
      stat("OLS DRIFT/d", fmt_signed(d$slope * 24, 2),
           sub = sprintf("p=%.3f", d$p_hac)),
      stat("HURST", sprintf("%.2f", d$hurst)),
      stat("VOL (ann)", fmt_pct(d$vol_ann, 1)),
      stat("N STEPS", as.character(d$n)),
      stat("SPREAD", fmt_pct(d$spread_pct))
    )
  })

  # Walk-forward CV summary ----------------------------------------------------
  output$card_wfcv_summary <- shiny::renderUI({
    w <- tryCatch(wfcv(), error = function(e) NULL)
    if (is.null(w)) {
      h <- input$wf_horizon %||% 7L
      need <- max(50L, 6L * as.integer(h))
      ph <- tryCatch(price_history(), error = function(e) NULL)
      have <- if (!is.null(ph)) nrow(ph) else 0L
      return(htmltools::tags$div(class = "muted",
        sprintf(
          "insufficient history for walk-forward CV — have %d, need >= max(50, 6*horizon) = %d (horizon=%d)",
          have, need, as.integer(h))))
    }
    htmltools::tags$div(class = "stat-grid stat-grid-3",
      stat("N TRADES", as.character(w$n_trades)),
      stat("HIT RATE", fmt_pct(w$hit_rate)),
      stat("BRIER", sprintf("%.3f", w$brier_point),
           sub = sprintf("[%.2f, %.2f]", w$brier_ci[1], w$brier_ci[2])),
      stat("IC", sprintf("%+.3f", w$ic_point),
           sub = sprintf("[%+.2f, %+.2f]", w$ic_ci[1], w$ic_ci[2])),
      stat("CI METHOD", toupper(w$ci_method)),
      stat("BOOT R", as.character(w$boot_b))
    )
  })

  output$card_reliability <- plotly::renderPlotly({
    w <- tryCatch(wfcv(), error = function(e) NULL)
    if (is.null(w) || nrow(w$trades) < 10) {
      return(plotly::plot_ly() |>
               plotly::layout(
                 paper_bgcolor = "#000000", plot_bgcolor = "#000000",
                 annotations = list(list(text = "no calibration data yet",
                                         showarrow = FALSE,
                                         font = list(color = "#52525b")))))
    }
    cal_post <- isotonic_via_probably(w$trades$p_up, w$trades$realized_up)
    rd_pre   <- reliability_diagram_data(w$trades$p_up, w$trades$realized_up)
    rd_post  <- reliability_diagram_data(cal_post, w$trades$realized_up)
    plotly::plot_ly() |>
      plotly::add_lines(x = c(0, 1), y = c(0, 1),
                        line = list(color = "rgba(82,82,91,0.6)",
                                    dash = "dot", width = 1),
                        name = "perfect", showlegend = FALSE) |>
      plotly::add_markers(x = rd_pre$mean_pred, y = rd_pre$observed_rate,
                          marker = list(color = "rgba(244,63,94,0.8)",
                                        size = pmax(6, sqrt(rd_pre$n))),
                          name = "pre-cal") |>
      plotly::add_markers(x = rd_post$mean_pred, y = rd_post$observed_rate,
                          marker = list(color = "rgba(16,185,129,0.95)",
                                        size = pmax(6, sqrt(rd_post$n))),
                          name = "post-cal (isotonic)") |>
      plotly::layout(
        paper_bgcolor = "#000000", plot_bgcolor = "#0a0a0a",
        font = list(color = "#fafafa", family = "JetBrains Mono"),
        xaxis = list(title = "forecast P(up)",
                     gridcolor = "rgba(63,63,70,0.25)", range = c(0, 1)),
        yaxis = list(title = "observed rate",
                     gridcolor = "rgba(63,63,70,0.25)", range = c(0, 1)),
        margin = list(l = 50, r = 20, t = 20, b = 50)
      ) |>
      plotly::config(displayModeBar = FALSE)
  })

  # Anthropic LLM cross-check (optional) ---------------------------------------
  output$card_anthropic_block <- shiny::renderUI({
    if (!anthropic_available()) {
      return(htmltools::tagList(
        section_header(9, "LLM CROSS-CHECK"),
        htmltools::tags$div(class = "panel muted",
          "Set ANTHROPIC_API_KEY to enable claude-opus-4-7 cross-checks.")
      ))
    }
    L <- listing()
    if (is.null(L)) return(NULL)
    rec <- recommendation()
    v <- verdict()
    g <- gates()
    d <- diagnostics()
    fc <- forecast()
    e <- ev_horizons()
    ev7 <- e[e$horizon == "7d", "e_ret"]
    p_up_h <- fc$summary$p_up[nrow(fc$summary)]
    # H6: pass the full verdict (status + failed-gate names + reasons)
    # so the LLM can describe WHY the gates blocked or downgraded the
    # signal, instead of guessing.
    summary_text <- shiny::isolate({
      anthropic_card_summary(
        card_meta = list(name = L$item$name, rarity = L$item$rarity,
                         ovr = L$item$ovr, team = L$item$team,
                         series = L$item$series),
        forecast_summary = list(ev = ev7, p_profit = NA, p_up = p_up_h,
                                drift_p = d$p_hac, hurst = d$hurst),
        recommendation = rec,
        verdict = v,
        gates = g
      )
    })
    htmltools::tagList(
      section_header(9, "LLM CROSS-CHECK"),
      htmltools::tags$div(class = "panel llm-block",
        not_a_signal_badge(),
        if (is.null(summary_text)) {
          htmltools::tags$div(class = "muted", "LLM unavailable.")
        } else htmltools::tags$p(summary_text)
      )
    )
  })
}

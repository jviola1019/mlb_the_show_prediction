#' Market scan: run microstructure, roster-upgrade, and forecast diagnostics
#' on a list of UUIDs and return a tidy data.frame ready for rendering.
#'
#' The three engines are kept separate:
#' - flip_* columns are executable bid/ask math only.
#' - upgrade_* columns are roster-threshold probabilities.
#' - forecast_* columns are non-executable time-series diagnostics.
#'
#' @param uuids character vector of 32-hex UUIDs.
#' @param horizon integer.
#' @param rate_delay numeric seconds between uncached fetches.
#' @param progress optional function(i, n, name) callback.
#' @param include_upgrade_stats logical; fetch MLB Stats API splits when TRUE.
#' @param today Date used for MLB stats windows.
#' @param now POSIXct used by validation gates; injectable for tests.
#' @return data.frame with executable flip math, upgrade probabilities,
#'   forecast diagnostics, and reason codes.
#' @export
scan_universe <- function(uuids, horizon = 7L, rate_delay = 1.5,
                          progress = NULL,
                          include_upgrade_stats = FALSE,
                          today = Sys.Date(),
                          now = Sys.time()) {
  uuids <- unique(stats::na.omit(as.character(uuids)))
  uuids <- uuids[vapply(uuids, is_valid_uuid, logical(1))]
  n <- length(uuids)
  if (n == 0L) return(.scan_empty_df())

  out <- vector("list", n)
  prev_was_uncached <- FALSE
  for (i in seq_len(n)) {
    u <- uuids[i]
    is_cached <- if (!is.null(.theshow_cache))
      .theshow_cache$exists(rlang::hash(list(u))) else FALSE
    if (prev_was_uncached) Sys.sleep(rate_delay)
    L <- tryCatch(get_listing(u),
                  error = function(e) list(error = conditionMessage(e)))
    prev_was_uncached <- !isTRUE(is_cached)
    nm <- L$item$name %||% L$listing_name %||% "?"
    if (is.function(progress)) progress(i, n, nm)
    if (!is.null(L$error)) {
      out[[i]] <- .scan_row_dropped(u, nm, L$error)
      next
    }

    liq <- liquidity_score(L$completed_orders %||% list())
    flip <- flip_economics(
      sell_price = L$best_sell_price,
      buy_price = L$best_buy_price,
      liquidity = liq
    )

    ph <- extract_price_history(L)
    rets <- if (nrow(ph) > 1L) log_returns(ph$price) else numeric(0)
    fc <- if (length(rets) >= 8L) {
      block_bootstrap(rets, current = L$best_sell_price,
                      horizon = horizon, n_sims = 1000L)
    } else NULL
    ev <- if (!is.null(fc)) {
      compute_ev(L$best_sell_price, L$best_buy_price %||% 0, fc, horizon)
    } else NULL
    wfcv <- if (nrow(ph) >= max(50L, 6L * horizon)) {
      tryCatch(
        walk_forward_cv(ph$price, horizon = horizon,
                        lookback = max(20L, 4L * horizon),
                        n_sims_per = 300L, boot_b = 300L,
                        ci_method = "block"),
        error = function(e) NULL
      )
    } else NULL

    cal_chk <- if (!is.null(wfcv) && nrow(wfcv$trades) >= 30L) {
      tryCatch(
        calibration_held_out_check(wfcv$trades$p_up,
                                   wfcv$trades$realized_up),
        error = function(e) NULL
      )
    } else NULL
    g <- validation_gates(price_history = ph, listing = L, wfcv = wfcv,
                          horizon = horizon, now = now,
                          calibration_ok = if (is.null(cal_chk)) FALSE
                          else cal_chk)
    v <- gating_verdict(g)
    tier <- tier_grade(verdict = v, gates = g,
                       liquidity_score = liq$score,
                       wfcv = wfcv,
                       holdout_brier_delta = if (is.null(cal_chk))
                         NA_real_ else cal_chk$delta)

    forecast_ev <- ev$expected_ret %||% NA_real_
    forecast_rec <- recommendation_score(
      ev = forecast_ev,
      drift_p = NA_real_, drift_slope = NA_real_,
      z30 = NA_real_, hurst = NA_real_,
      spread_pct = flip$spread_pct,
      cv_ic_point = wfcv$ic_point %||% NA_real_,
      cv_ic_upper = if (length(wfcv$ic_ci %||% NULL) == 2L) wfcv$ic_ci[2]
                    else NA_real_
    )
    forecast_direction <- if (!is.finite(forecast_ev)) {
      "FORECAST UNAVAILABLE"
    } else if (forecast_ev <= -0.01) {
      "FORECAST BEARISH"
    } else if (forecast_ev >= 0.01) {
      "FORECAST BULLISH"
    } else {
      "FORECAST FLAT"
    }

    stats_bundle <- NULL
    if (isTRUE(include_upgrade_stats)) {
      stats_bundle <- tryCatch(
        get_recent_vs_season_stats(nm, role = NULL, today = today),
        error = function(e) NULL
      )
    }
    if (is.null(stats_bundle)) {
      stats_bundle <- list(recent = list(), season = list(),
                           role = "hitter", player = NULL)
    }
    upgrade <- roster_upgrade_engine(
      stats_recent = stats_bundle$recent %||% list(),
      stats_season = stats_bundle$season %||% list(),
      role = stats_bundle$role %||% "hitter",
      current_ovr = L$item$ovr %||% NA_integer_,
      rarity = L$item$rarity %||% NA_character_,
      new_rank = L$item$new_rank %||% NA_real_
    )
    py_score <- tryCatch(
      python_score_card(list(
        uuid = u,
        name = nm,
        raw_ask = L$best_sell_price %||% NA_real_,
        raw_bid = L$best_buy_price %||% NA_real_,
        liquidity_score = liq$score %||% NA_real_,
        liquidity_n = liq$n %||% 0L,
        liquidity_recent = liq$recent %||% NA_integer_,
        current_ovr = L$item$ovr %||% NA_integer_,
        rarity = L$item$rarity %||% NA_character_,
        new_rank = L$item$new_rank %||% NA_real_,
        role = stats_bundle$role %||% "hitter",
        recent = stats_bundle$recent %||% list(),
        season = stats_bundle$season %||% list()
      )),
      error = function(e) NULL
    )
    py_flip <- tryCatch(python_result_to_flip(py_score),
                        error = function(e) NULL)
    py_upgrade <- tryCatch(python_result_to_upgrade(py_score),
                           error = function(e) NULL)
    if (!is.null(py_flip)) flip <- py_flip
    if (!is.null(py_upgrade)) upgrade <- py_upgrade

    scan_status <- if (!flip$executable && upgrade$action == "AVOID") {
      "INVALID"
    } else {
      "VALID"
    }

    out[[i]] <- data.frame(
      uuid = u,
      name = nm,
      rarity = L$item$rarity %||% NA_character_,
      ovr = as.integer(L$item$ovr %||% NA_integer_),
      team = L$item$team %||% NA_character_,
      ask = as.numeric(L$best_sell_price %||% NA_real_),
      bid = as.numeric(L$best_buy_price %||% NA_real_),
      raw_ask = as.numeric(L$best_sell_price %||% NA_real_),
      raw_bid = as.numeric(L$best_buy_price %||% NA_real_),
      after_tax_sale = flip$after_tax_sale,
      flip_profit = flip$profit,
      flip_roi = flip$roi,
      spread_pct = flip$spread_pct,
      liquidity_score = flip$liquidity_score,
      liquidity_n = flip$liquidity_n,
      liquidity_recent = flip$liquidity_recent,
      flip_executable = flip$executable,
      flip_action = flip$action,
      flip_reason_codes = flip$reason_codes_csv,
      flip_failed_gates = flip$failed_gates_csv,
      forecast_ev_7d = forecast_ev,
      forecast_direction = forecast_direction,
      forecast_p_up_7d = if (!is.null(fc)) fc$summary$p_up[horizon + 1L]
                         else NA_real_,
      forecast_score = if (is.null(forecast_rec$score)) NA_integer_
                       else forecast_rec$score,
      forecast_action = forecast_rec$action,
      ev_7d = forecast_ev,
      p_up_7d = if (!is.null(fc)) fc$summary$p_up[horizon + 1L]
                else NA_real_,
      score = if (is.null(forecast_rec$score)) NA_integer_
              else forecast_rec$score,
      action = forecast_rec$action,
      direction = if (forecast_direction == "FORECAST BULLISH") "▲"
                  else if (forecast_direction == "FORECAST BEARISH") "▼"
                  else "—",
      new_rank = upgrade$new_rank,
      next_threshold = upgrade$next_threshold,
      distance_to_threshold = upgrade$distance_to_threshold,
      distance_to_85 = upgrade$distance_to_85 %||% NA_real_,
      distance_to_90 = upgrade$distance_to_90 %||% NA_real_,
      p_upgrade = upgrade$p_upgrade,
      p_downgrade = upgrade$p_downgrade,
      p_cross_next_threshold = upgrade$p_cross_next_threshold,
      p_cross_85 = upgrade$p_cross_85,
      p_cross_90 = upgrade$p_cross_90,
      upgrade_confidence = upgrade$confidence,
      upgrade_score = upgrade$upgrade_score,
      upgrade_action = upgrade$action,
      upgrade_reason_codes = upgrade$reason_codes_csv,
      scan_status = scan_status,
      verdict_status = v$status,
      tier = tier$tier,
      gates_failed_csv = paste(v$failed, collapse = ","),
      n_trades = wfcv$n_trades %||% 0L,
      ic_point = wfcv$ic_point %||% NA_real_,
      ic_ci_lo = if (length(wfcv$ic_ci %||% NULL) == 2L) wfcv$ic_ci[1]
                 else NA_real_,
      ic_ci_hi = if (length(wfcv$ic_ci %||% NULL) == 2L) wfcv$ic_ci[2]
                 else NA_real_,
      stringsAsFactors = FALSE
    )
  }
  do.call(rbind, out)
}

.scan_empty_df <- function() {
  data.frame(
    uuid = character(0), name = character(0), rarity = character(0),
    ovr = integer(0), team = character(0),
    ask = numeric(0), bid = numeric(0),
    raw_ask = numeric(0), raw_bid = numeric(0),
    after_tax_sale = numeric(0), flip_profit = numeric(0),
    flip_roi = numeric(0), spread_pct = numeric(0),
    liquidity_score = numeric(0), liquidity_n = integer(0),
    liquidity_recent = integer(0),
    flip_executable = logical(0), flip_action = character(0),
    flip_reason_codes = character(0), flip_failed_gates = character(0),
    forecast_ev_7d = numeric(0), forecast_direction = character(0),
    forecast_p_up_7d = numeric(0), forecast_score = integer(0),
    forecast_action = character(0),
    ev_7d = numeric(0), p_up_7d = numeric(0),
    score = integer(0), action = character(0), direction = character(0),
    new_rank = numeric(0), next_threshold = numeric(0),
    distance_to_threshold = numeric(0),
    distance_to_85 = numeric(0), distance_to_90 = numeric(0),
    p_upgrade = numeric(0), p_downgrade = numeric(0),
    p_cross_next_threshold = numeric(0), p_cross_85 = numeric(0),
    p_cross_90 = numeric(0), upgrade_confidence = numeric(0),
    upgrade_score = numeric(0), upgrade_action = character(0),
    upgrade_reason_codes = character(0), scan_status = character(0),
    verdict_status = character(0), tier = character(0),
    gates_failed_csv = character(0),
    n_trades = integer(0), ic_point = numeric(0),
    ic_ci_lo = numeric(0), ic_ci_hi = numeric(0),
    stringsAsFactors = FALSE
  )
}

.scan_row_dropped <- function(uuid, name, reason) {
  data.frame(
    uuid = uuid, name = name,
    rarity = NA_character_, ovr = NA_integer_, team = NA_character_,
    ask = NA_real_, bid = NA_real_,
    raw_ask = NA_real_, raw_bid = NA_real_,
    after_tax_sale = NA_real_, flip_profit = NA_real_,
    flip_roi = NA_real_, spread_pct = NA_real_,
    liquidity_score = NA_real_, liquidity_n = 0L,
    liquidity_recent = NA_integer_,
    flip_executable = FALSE, flip_action = "NO TRADE",
    flip_reason_codes = sprintf("FETCH_ERROR:%s", reason),
    flip_failed_gates = "fetch",
    forecast_ev_7d = NA_real_, forecast_direction = "FORECAST UNAVAILABLE",
    forecast_p_up_7d = NA_real_, forecast_score = NA_integer_,
    forecast_action = "HOLD",
    ev_7d = NA_real_, p_up_7d = NA_real_, score = NA_integer_,
    action = "ABSTAIN", direction = "—",
    new_rank = NA_real_, next_threshold = NA_real_,
    distance_to_threshold = NA_real_,
    distance_to_85 = NA_real_, distance_to_90 = NA_real_,
    p_upgrade = NA_real_, p_downgrade = NA_real_,
    p_cross_next_threshold = NA_real_, p_cross_85 = NA_real_,
    p_cross_90 = NA_real_, upgrade_confidence = NA_real_,
    upgrade_score = NA_real_, upgrade_action = "AVOID",
    upgrade_reason_codes = sprintf("FETCH_ERROR:%s", reason),
    scan_status = "INVALID",
    verdict_status = "NOT INVESTABLE",
    tier = "ABSTAIN",
    gates_failed_csv = sprintf("fetch_error:%s", reason),
    n_trades = 0L, ic_point = NA_real_,
    ic_ci_lo = NA_real_, ic_ci_hi = NA_real_,
    stringsAsFactors = FALSE
  )
}

#' Partition a scan result into explicit engine sections.
#' @export
scan_partition <- function(scan_df) {
  if (nrow(scan_df) == 0L) {
    return(list(flip_buy = scan_df, upgrade_buy = scan_df,
                holds = scan_df, sell = scan_df, dropped = scan_df,
                buy = scan_df, observe = scan_df))
  }

  if (!"flip_action" %in% names(scan_df) ||
      !"upgrade_action" %in% names(scan_df)) {
    inv <- scan_df$verdict_status == "INVESTABLE"
    obs <- scan_df$verdict_status == "OBSERVATIONAL ONLY"
    drop <- scan_df$verdict_status == "NOT INVESTABLE"
    buy <- scan_df[inv & !is.na(scan_df$score) & scan_df$score >= 1L, ,
                   drop = FALSE]
    buy <- buy[order(-buy$score, -buy$ev_7d), , drop = FALSE]
    sell <- scan_df[inv & !is.na(scan_df$score) & scan_df$score <= -1L, ,
                    drop = FALSE]
    sell <- sell[order(sell$score, sell$ev_7d), , drop = FALSE]
    observe <- scan_df[obs, , drop = FALSE]
    dropped <- scan_df[drop, , drop = FALSE]
    return(list(flip_buy = buy, upgrade_buy = scan_df[FALSE, , drop = FALSE],
                holds = observe, sell = sell, dropped = dropped,
                buy = buy, observe = observe))
  }

  invalid <- scan_df$scan_status == "INVALID" |
    grepl("^fetch_error", scan_df$gates_failed_csv %||% "", ignore.case = TRUE)
  flip_buy <- scan_df[!invalid & scan_df$flip_action == "BUY", ,
                      drop = FALSE]
  flip_buy <- flip_buy[order(-flip_buy$flip_roi, -flip_buy$flip_profit),
                       , drop = FALSE]

  upgrade_buy <- scan_df[!invalid &
                           scan_df$upgrade_action == "BUY SPECULATIVE" &
                           scan_df$flip_action != "BUY", ,
                         drop = FALSE]
  upgrade_buy <- upgrade_buy[order(-upgrade_buy$upgrade_score,
                                   upgrade_buy$distance_to_threshold),
                             , drop = FALSE]

  sell <- scan_df[!invalid &
                    (scan_df$flip_action == "SELL" |
                       scan_df$upgrade_action == "SELL"), ,
                  drop = FALSE]
  sell <- sell[order(sell$flip_roi, -sell$p_downgrade), , drop = FALSE]

  selected <- invalid |
    scan_df$uuid %in% c(flip_buy$uuid, upgrade_buy$uuid, sell$uuid)
  holds <- scan_df[!selected, , drop = FALSE]
  holds <- holds[order(holds$forecast_direction, -holds$upgrade_score),
                 , drop = FALSE]
  dropped <- scan_df[invalid, , drop = FALSE]

  list(flip_buy = flip_buy, upgrade_buy = upgrade_buy, holds = holds,
       sell = sell, dropped = dropped,
       buy = flip_buy, observe = holds)
}

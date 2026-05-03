#' Market scan: run the full quant pipeline on a list of UUIDs and return
#' a tidy data.frame ready for leaderboard rendering.
#'
#' Honours rate limits: a `Sys.sleep(rate_delay)` between *uncached* fetches
#' (memoised hits don't sleep).
#'
#' Validation gates are applied per card; the verdict drives whether the
#' card appears on a BUY/SELL leaderboard, an OBSERVATIONAL list, or is
#' silently DROPPED.

#' @param uuids character vector of 32-hex UUIDs.
#' @param horizon integer.
#' @param rate_delay numeric seconds between uncached fetches.
#' @param progress optional `function(i, n, name)` callback.
#' @return data.frame with columns:
#'   uuid, name, rarity, ovr, team, ask, bid, spread_pct,
#'   ev_7d, p_up_7d, score, action, direction,
#'   verdict_status, gates_failed_csv,
#'   n_trades, ic_point, ic_ci_lo, ic_ci_hi.
#' @export
scan_universe <- function(uuids, horizon = 7L, rate_delay = 1.5,
                          progress = NULL) {
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
    L <- tryCatch(get_listing(u), error = function(e) list(error = conditionMessage(e)))
    prev_was_uncached <- !isTRUE(is_cached)
    nm <- L$item$name %||% L$listing_name %||% "?"
    if (is.function(progress)) progress(i, n, nm)
    if (!is.null(L$error)) {
      out[[i]] <- .scan_row_dropped(u, nm, L$error)
      next
    }
    ph <- extract_price_history(L)
    rets <- if (nrow(ph) > 1L) log_returns(ph$price) else numeric(0)
    fc <- if (length(rets) >= 8L)
            block_bootstrap(rets, current = L$best_sell_price,
                            horizon = horizon, n_sims = 1000L) else NULL
    ev <- if (!is.null(fc))
            compute_ev(L$best_sell_price, L$best_buy_price %||% 0, fc,
                       horizon) else NULL
    wfcv <- if (nrow(ph) >= max(50L, 6L * horizon)) {
      tryCatch(walk_forward_cv(ph$price, horizon = horizon,
                               lookback = max(20L, 4L * horizon),
                               n_sims_per = 300L, boot_b = 300L,
                               ci_method = "block"),
               error = function(e) NULL)
    } else NULL

    g <- validation_gates(price_history = ph, listing = L, wfcv = wfcv,
                          horizon = horizon)
    v <- gating_verdict(g)
    spread_pct <- if (isTRUE(L$best_sell_price > 0))
      (L$best_sell_price - (L$best_buy_price %||% 0)) / L$best_sell_price
      else NA_real_
    rec <- recommendation_score(
      ev = ev$expected_ret %||% NA_real_,
      drift_p = NA_real_, drift_slope = NA_real_,
      z30 = NA_real_,
      hurst = NA_real_,
      spread_pct = spread_pct,
      cv_ic_point = wfcv$ic_point %||% NA_real_,
      cv_ic_upper = if (length(wfcv$ic_ci %||% NULL) == 2L) wfcv$ic_ci[2]
                    else NA_real_
    )
    out[[i]] <- data.frame(
      uuid = u,
      name = nm,
      rarity = L$item$rarity %||% NA_character_,
      ovr = as.integer(L$item$ovr %||% NA_integer_),
      team = L$item$team %||% NA_character_,
      ask = as.numeric(L$best_sell_price %||% NA_real_),
      bid = as.numeric(L$best_buy_price %||% NA_real_),
      spread_pct = spread_pct,
      ev_7d = ev$expected_ret %||% NA_real_,
      p_up_7d = if (!is.null(fc)) fc$summary$p_up[horizon + 1L]
                else NA_real_,
      score = if (is.null(rec$score)) NA_integer_ else rec$score,
      action = rec$action,
      direction = if (!is.na(rec$score) && rec$score > 0) "▲"
                  else if (!is.na(rec$score) && rec$score < 0) "▼" else "—",
      verdict_status = v$status,
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
  data.frame(uuid=character(0), name=character(0), rarity=character(0),
             ovr=integer(0), team=character(0),
             ask=numeric(0), bid=numeric(0), spread_pct=numeric(0),
             ev_7d=numeric(0), p_up_7d=numeric(0),
             score=integer(0), action=character(0), direction=character(0),
             verdict_status=character(0), gates_failed_csv=character(0),
             n_trades=integer(0), ic_point=numeric(0),
             ic_ci_lo=numeric(0), ic_ci_hi=numeric(0),
             stringsAsFactors=FALSE)
}

.scan_row_dropped <- function(uuid, name, reason) {
  data.frame(
    uuid = uuid, name = name,
    rarity = NA_character_, ovr = NA_integer_, team = NA_character_,
    ask = NA_real_, bid = NA_real_, spread_pct = NA_real_,
    ev_7d = NA_real_, p_up_7d = NA_real_, score = NA_integer_,
    action = "ABSTAIN", direction = "—",
    verdict_status = "NOT INVESTABLE",
    gates_failed_csv = sprintf("fetch_error:%s", reason),
    n_trades = 0L, ic_point = NA_real_,
    ic_ci_lo = NA_real_, ic_ci_hi = NA_real_,
    stringsAsFactors = FALSE
  )
}

#' Partition a scan result into BUY / SELL / OBSERVATIONAL / DROPPED.
#' @export
scan_partition <- function(scan_df) {
  if (nrow(scan_df) == 0L) {
    return(list(buy = scan_df, sell = scan_df, observe = scan_df,
                dropped = scan_df))
  }
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
  list(buy = buy, sell = sell, observe = observe, dropped = dropped)
}

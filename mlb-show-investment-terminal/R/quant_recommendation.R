#' Recommendation scoring — verbatim port of v3.3 lines 688-708.
#'
#' Aggregates EV, OLS drift significance, z-score on rolling 30-step price,
#' Hurst regime, spread, and walk-forward CV credibility into an integer score
#' that maps to STRONG BUY / BUY / HOLD / SELL / STRONG SELL.

#' @param ev numeric expected return on a 7d hold (e.g. 0.06 = 6%).
#' @param drift_p numeric HAC p-value of OLS log-price slope. NA allowed.
#' @param drift_slope numeric OLS slope. NA allowed.
#' @param z30 numeric z-score of current price vs 30-step rolling mean.
#' @param hurst numeric Hurst exponent on log returns.
#' @param spread_pct numeric (ask-bid)/ask.
#' @param cv_ic_point numeric walk-forward IC point estimate. NA allowed.
#' @param cv_ic_upper numeric upper bound of IC bootstrap CI. NA allowed.
#' @return list(score, action, flags) where flags is a list of
#'   list(level = c("bull","bear","warn","info"), text = character)
#' @export
recommendation_score <- function(ev,
                                 drift_p = NA_real_, drift_slope = NA_real_,
                                 z30 = NA_real_,
                                 hurst = NA_real_,
                                 spread_pct = NA_real_,
                                 cv_ic_point = NA_real_,
                                 cv_ic_upper = NA_real_) {
  score <- 0L
  flags <- list()

  # EV contribution
  if (!is.na(ev)) {
    if (ev > 0.05) {
      score <- score + 2L
      flags[[length(flags) + 1L]] <- list(level = "bull",
                                          text = sprintf("+EV>5%% (%.1f%%)",
                                                         ev * 100))
    } else if (ev > 0.01) {
      score <- score + 1L
      flags[[length(flags) + 1L]] <- list(level = "bull",
                                          text = sprintf("+EV (%.1f%%)",
                                                         ev * 100))
    } else if (ev < -0.05) {
      score <- score - 2L
      flags[[length(flags) + 1L]] <- list(level = "bear",
                                          text = sprintf("-EV<-5%% (%.1f%%)",
                                                         ev * 100))
    } else if (ev < -0.01) {
      score <- score - 1L
      flags[[length(flags) + 1L]] <- list(level = "bear",
                                          text = sprintf("-EV (%.1f%%)",
                                                         ev * 100))
    }
  }

  # Drift significance
  if (!is.na(drift_p) && !is.na(drift_slope) && drift_p < 0.05) {
    if (drift_slope > 0) {
      score <- score + 1L
      flags[[length(flags) + 1L]] <- list(level = "bull", text = "drift sig+")
    } else if (drift_slope < 0) {
      score <- score - 1L
      flags[[length(flags) + 1L]] <- list(level = "bear", text = "drift sig-")
    }
  }

  # Mean-reversion overlay (z30)
  if (!is.na(z30)) {
    if (z30 < -1.5) {
      score <- score + 1L
      flags[[length(flags) + 1L]] <- list(level = "bull", text = "oversold")
    } else if (z30 > 1.5) {
      score <- score - 1L
      flags[[length(flags) + 1L]] <- list(level = "bear", text = "overbought")
    }
  }

  # Spread warning
  if (!is.na(spread_pct) && spread_pct > 0.15) {
    flags[[length(flags) + 1L]] <- list(level = "warn",
                                        text = sprintf("wide spread (%.0f%%)",
                                                       spread_pct * 100))
  }

  # Walk-forward CV credibility flags
  if (!is.na(cv_ic_upper) && cv_ic_upper < 0) {
    flags[[length(flags) + 1L]] <- list(level = "warn",
                                        text = "CV IC<0 (sig)")
  } else if (!is.na(cv_ic_point) && cv_ic_point < -0.10) {
    flags[[length(flags) + 1L]] <- list(level = "warn", text = "CV IC<0")
  }

  # Hurst regime info
  if (!is.na(hurst)) {
    if (hurst > 0.6) {
      flags[[length(flags) + 1L]] <- list(level = "info", text = "trending")
    } else if (hurst < 0.4) {
      flags[[length(flags) + 1L]] <- list(level = "info", text = "mean-revert")
    }
  }

  action <- if (score >= 3L) "STRONG BUY"
            else if (score >= 1L) "BUY"
            else if (score <= -3L) "STRONG SELL"
            else if (score <= -1L) "SELL"
            else "HOLD"

  list(score = score, action = action, flags = flags)
}

#' Walk-forward cross-validation for the block-bootstrap forecast.
#'
#' At each time t in [lookback+1 .. N-horizon], fit a block-bootstrap on the
#' returns within [t-lookback, t-1] and forecast `horizon` steps. Compare the
#' bootstrap p_up (probability of price-up over horizon) to the realized
#' direction. Compute Brier score on (p_up vs realized_up) and Information
#' Coefficient (Spearman rank correlation between forecast median return and
#' realized return) per trade.
#'
#' Two CI methods on Brier and IC:
#'   - "block":     stationary block bootstrap on the time-series of per-trade
#'                  Brier residuals (correct under autocorrelated trades).
#'   - "per_trade": iid bootstrap (treats trades as independent — narrower CI).

#' Walk-forward CV with bootstrap CIs.
#'
#' @param prices numeric vector of prices, length >= lookback + horizon + 1.
#' @param horizon integer steps ahead to forecast.
#' @param lookback integer training window length.
#' @param n_sims_per integer bootstrap sims per fold.
#' @param boot_b integer outer-bootstrap replicates for the CI on Brier/IC.
#' @param ci_method "block" or "per_trade".
#' @param conf numeric confidence level, default 0.90.
#' @return list with trades, brier_point/ci, ic_point/ci, hit_rate, n_trades,
#'   ci_method, boot_b, p_up, realized_up. NULL if insufficient data.
#' @export
walk_forward_cv <- function(prices, horizon, lookback,
                            n_sims_per = 1000L, boot_b = 1000L,
                            ci_method = c("block", "per_trade"),
                            conf = 0.90) {
  ci_method <- match.arg(ci_method)
  prices <- as.numeric(prices)
  prices <- prices[is.finite(prices) & prices > 0]
  N <- length(prices)
  if (N < lookback + horizon + 1L) return(NULL)
  # Degenerate input: zero variance -> bootstrap is meaningless.
  if (stats::sd(log_returns(prices)) <= .Machine$double.eps) return(NULL)

  starts <- seq.int(lookback + 1L, N - horizon)
  if (length(starts) < 10L) return(NULL)

  trades <- vector("list", length(starts))
  for (k in seq_along(starts)) {
    t <- starts[k]
    win <- prices[(t - lookback):(t - 1L)]
    rets <- log_returns(win)
    if (length(rets) < 8L) next
    fc <- block_bootstrap(rets, current = prices[t - 1L], horizon = horizon,
                          n_sims = n_sims_per)
    if (is.null(fc)) next
    final_paths <- fc$paths[, horizon + 1L]
    final_paths <- final_paths[is.finite(final_paths)]
    if (length(final_paths) == 0L) next

    p_up_t <- mean(final_paths > prices[t - 1L])
    forecast_med_ret <- median(final_paths) / prices[t - 1L] - 1
    realized <- prices[t - 1L + horizon]
    realized_up <- as.integer(realized > prices[t - 1L])
    realized_ret <- realized / prices[t - 1L] - 1

    trades[[k]] <- data.frame(
      t_idx = t,
      p_up = p_up_t,
      realized_up = realized_up,
      forecast_ret = forecast_med_ret,
      realized_ret = realized_ret,
      brier_t = (p_up_t - realized_up)^2
    )
  }
  trades <- do.call(rbind, Filter(Negate(is.null), trades))
  if (is.null(trades) || nrow(trades) < 10L) return(NULL)

  # Point estimates
  brier_point <- mean(trades$brier_t)
  ic_point <- suppressWarnings(stats::cor(
    trades$forecast_ret, trades$realized_ret, method = "spearman"
  ))
  if (is.na(ic_point)) ic_point <- 0

  # Bootstrap CIs
  alpha <- (1 - conf) / 2
  q_lo <- alpha; q_hi <- 1 - alpha

  brier_ci <- ic_ci <- c(NA_real_, NA_real_)
  if (ci_method == "block") {
    bl <- block_length(trades$brier_t)
    brier_boot <- tryCatch(
      boot::tsboot(trades$brier_t, statistic = function(x) mean(x),
                   R = boot_b, l = bl, sim = "geom"),
      error = function(e) NULL
    )
    if (!is.null(brier_boot)) {
      brier_ci <- as.numeric(stats::quantile(brier_boot$t,
                                             c(q_lo, q_hi), na.rm = TRUE))
    }
    ic_pairs <- cbind(trades$forecast_ret, trades$realized_ret)
    ic_boot <- tryCatch(
      boot::tsboot(ic_pairs, statistic = function(m) {
        suppressWarnings(stats::cor(m[, 1], m[, 2], method = "spearman"))
      }, R = boot_b, l = block_length(trades$forecast_ret), sim = "geom"),
      error = function(e) NULL
    )
    if (!is.null(ic_boot)) {
      ic_ci <- as.numeric(stats::quantile(ic_boot$t,
                                          c(q_lo, q_hi), na.rm = TRUE))
    }
  } else {
    brier_boot <- tryCatch(
      boot::boot(trades$brier_t,
                 statistic = function(x, i) mean(x[i]),
                 R = boot_b),
      error = function(e) NULL
    )
    if (!is.null(brier_boot)) {
      brier_ci <- as.numeric(stats::quantile(brier_boot$t,
                                             c(q_lo, q_hi), na.rm = TRUE))
    }
    ic_pairs <- cbind(trades$forecast_ret, trades$realized_ret)
    ic_boot <- tryCatch(
      boot::boot(ic_pairs, statistic = function(m, i) {
        suppressWarnings(stats::cor(m[i, 1], m[i, 2], method = "spearman"))
      }, R = boot_b),
      error = function(e) NULL
    )
    if (!is.null(ic_boot)) {
      ic_ci <- as.numeric(stats::quantile(ic_boot$t,
                                          c(q_lo, q_hi), na.rm = TRUE))
    }
  }

  list(
    trades = trades,
    brier_point = brier_point,
    brier_ci = brier_ci,
    ic_point = ic_point,
    ic_ci = ic_ci,
    hit_rate = mean(trades$realized_up == as.integer(trades$p_up >= 0.5)),
    n_trades = nrow(trades),
    ci_method = ci_method,
    boot_b = boot_b,
    p_up = trades$p_up,
    realized_up = trades$realized_up
  )
}

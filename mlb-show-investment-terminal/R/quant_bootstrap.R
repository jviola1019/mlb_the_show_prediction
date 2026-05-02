#' Block bootstrap forecasting (Politis-Romano stationary)
#'
#' Implements both the classic stationary block bootstrap (Politis & Romano 1994)
#' and the automatic block-length selector b.star (Politis & White 2004) which
#' is theoretically optimal for the spectral-density estimation problem.
#'
#' The stationary block bootstrap differs from Künsch's moving-block bootstrap
#' in that block lengths are random (geometric distribution) rather than fixed;
#' this preserves stationarity of the resampled series.
#'
#' For our use case (log-returns of card prices that may exhibit autocorrelation
#' from market microstructure / trader behavior), preserving short-range serial
#' dependence is critical. iid resampling would understate variance.

#' Optimal block length via Politis-White b.star.
#'
#' Wraps `np::b.star` if available; falls back to the heuristic
#' L = max(3, floor(N^0.4)) used in the original Politis-Romano paper as a
#' rule of thumb for stationary block bootstrap.
#'
#' @param x numeric vector. Time series (typically log returns).
#' @return integer. Recommended mean block length.
#' @export
block_length <- function(x) {
  n <- length(x)
  if (n < 8L) return(max(3L, floor(n / 2)))
  # Try np::b.star if installed; this is Politis-White optimal selector
  if (requireNamespace("np", quietly = TRUE)) {
    out <- tryCatch(
      np::b.star(x, round = TRUE)$b.star,
      error = function(e) NA_real_,
      warning = function(w) NA_real_
    )
    if (!is.na(out) && is.finite(out) && out >= 1L) return(max(3L, as.integer(out)))
  }
  # Fall back to N^0.4 rule-of-thumb
  max(3L, as.integer(floor(n^0.4)))
}

#' Stationary block bootstrap of a log-return series.
#'
#' Generates `n_sims` price paths of length `horizon` starting from `current`.
#' Each path resamples blocks of returns with random geometric lengths
#' (mean = block_len), preserving short-range autocorrelation.
#'
#' @param returns numeric. Log returns (can be obtained via `log_returns()`).
#' @param current numeric. Current price (path start).
#' @param horizon integer. Number of steps ahead.
#' @param n_sims integer. Number of bootstrap paths. Default 2000.
#' @param block_len integer or NULL. If NULL, computed via `block_length()`.
#' @param method "stationary" (geometric, Politis-Romano) or "moving" (fixed, Künsch).
#'
#' @return list with:
#'   - paths: matrix [n_sims x (horizon+1)] of prices
#'   - summary: data.frame [horizon+1 rows] with p5/p25/p50/p75/p95/p_up
#'   - block_length: integer, the (mean) block length used
#'   - method: character
#'
#' @export
block_bootstrap <- function(returns, current, horizon,
                            n_sims = 2000L,
                            block_len = NULL,
                            method = c("stationary", "moving")) {
  method <- match.arg(method)
  returns <- as.numeric(returns)
  returns <- returns[is.finite(returns)]

  if (length(returns) < 8L || current <= 0 || horizon < 1L) {
    return(NULL)
  }

  L <- block_len %||% block_length(returns)
  N <- length(returns)
  cols <- horizon + 1L
  paths <- matrix(NA_real_, nrow = n_sims, ncol = cols)
  paths[, 1L] <- current

  log_current <- log(current)
  max_start <- N - L + 1L

  for (i in seq_len(n_sims)) {
    log_p <- log_current
    h <- 0L
    while (h < horizon) {
      # Pick block start uniformly
      start <- sample.int(max_start, size = 1L)
      # Block length: geometric for stationary, fixed L for moving
      this_len <- if (method == "stationary") {
        # E[geometric] = 1/p, choose p = 1/L
        rgeom(1L, prob = 1 / L) + 1L
      } else {
        L
      }
      this_len <- min(this_len, horizon - h)
      end <- min(start + this_len - 1L, N)
      if (end < start) end <- start  # safety
      block <- returns[start:end]
      for (k in seq_along(block)) {
        h <- h + 1L
        log_p <- log_p + block[k]
        paths[i, h + 1L] <- exp(log_p)
        if (h >= horizon) break
      }
    }
  }

  # Per-step percentile + p_up summary
  summary_df <- data.frame(
    step = 0:horizon,
    p5  = apply(paths, 2, stats::quantile, probs = 0.05, na.rm = TRUE),
    p25 = apply(paths, 2, stats::quantile, probs = 0.25, na.rm = TRUE),
    p50 = apply(paths, 2, stats::quantile, probs = 0.50, na.rm = TRUE),
    p75 = apply(paths, 2, stats::quantile, probs = 0.75, na.rm = TRUE),
    p95 = apply(paths, 2, stats::quantile, probs = 0.95, na.rm = TRUE),
    p_up = colMeans(paths > current, na.rm = TRUE),
    stringsAsFactors = FALSE
  )

  list(
    paths = paths,
    summary = summary_df,
    block_length = L,
    method = method
  )
}

#' Compute Expected Value with The Show 10% market tax + bid/ask spread.
#'
#' Models the trader's cycle: pay current ask, exit at forecast price * (bid/ask)
#' to capture spread, then 10% tax on sell-side proceeds.
#'
#' @param ask numeric. Current best sell price (you pay).
#' @param bid numeric. Current best buy price (you receive on sale).
#' @param fc list. Output of `block_bootstrap()`.
#' @param horizon integer. Step at which to evaluate (typically end of cone).
#'
#' @return list with expected_ret, p_profit, p5/p50/p95 of return,
#'   kelly fraction (full + half), breakeven price.
#'
#' @export
compute_ev <- function(ask, bid, fc, horizon) {
  if (is.null(fc) || ask <= 0 || horizon < 1L) return(NULL)
  TAX <- 0.10
  final <- fc$paths[, horizon + 1L]
  final <- final[is.finite(final)]
  if (length(final) == 0L) return(NULL)

  spread_ratio <- if (bid > 0) bid / ask else 0.9
  rets <- (final * spread_ratio * (1 - TAX) - ask) / ask

  expected_ret <- mean(rets, na.rm = TRUE)
  p_profit <- mean(rets > 0, na.rm = TRUE)
  wins <- rets[rets > 0]
  losses <- rets[rets < 0]
  win_size <- if (length(wins)) mean(wins) else 0
  loss_size <- if (length(losses)) -mean(losses) else 0
  b <- if (loss_size > 0) win_size / loss_size else 0
  kelly <- if (b > 0) max(0, (p_profit * b - (1 - p_profit)) / b) else 0

  list(
    expected_ret = expected_ret,
    p_profit = p_profit,
    p5_ret  = stats::quantile(rets, 0.05, na.rm = TRUE, names = FALSE),
    p50_ret = stats::quantile(rets, 0.50, na.rm = TRUE, names = FALSE),
    p95_ret = stats::quantile(rets, 0.95, na.rm = TRUE, names = FALSE),
    kelly = kelly,
    kelly_half = kelly / 2,
    breakeven = ask / ((1 - TAX) * spread_ratio)
  )
}

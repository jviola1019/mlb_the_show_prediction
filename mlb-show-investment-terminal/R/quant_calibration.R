#' Isotonic calibration for binary probability forecasts.
#'
#' Two implementations are provided and cross-checked in tests:
#'   - `isotonic_via_probably`: production path using `probably::cal_estimate_isotonic`
#'   - `isotonic_pav_custom`:   reference Pool-Adjacent-Violators implementation
#'
#' Why isotonic: block-bootstrap p_up is calibrated against a random walk null,
#' which is rarely true for card markets (volume clusters, payout cycles). A
#' light non-parametric monotone correction can buy meaningful Brier reduction
#' without imposing a parametric form.

#' Probability-of-up calibration via `probably`.
#'
#' @param preds numeric in [0,1].
#' @param truth integer 0/1 outcome.
#' @return numeric same length as preds, monotone non-decreasing in preds.
#' @export
isotonic_via_probably <- function(preds, truth) {
  preds <- as.numeric(preds)
  truth <- as.integer(truth)
  stopifnot(length(preds) == length(truth))
  if (length(preds) == 0L) return(numeric(0))

  df <- data.frame(
    .pred_yes = preds,
    truth = factor(truth, levels = c("1", "0"))  # event_level = "first" needs "1" first
  )
  cal <- tryCatch(
    probably::cal_estimate_isotonic(df, truth = truth, estimate = .pred_yes),
    error = function(e) NULL
  )
  if (is.null(cal)) return(isotonic_pav_custom(preds, truth))
  out <- tryCatch(
    probably::cal_apply(df, cal),
    error = function(e) NULL
  )
  if (is.null(out) || !".pred_yes" %in% names(out)) {
    return(isotonic_pav_custom(preds, truth))
  }
  as.numeric(out$.pred_yes)
}

#' Reference PAV (pool-adjacent-violators) isotonic regression.
#'
#' Stable tie-breaking via `order(preds, seq_along(preds))` ensures the
#' production path and reference path agree at numerical tolerance.
#'
#' @param preds numeric in [0,1].
#' @param truth integer 0/1 outcome.
#' @return numeric same length as preds.
#' @export
isotonic_pav_custom <- function(preds, truth) {
  preds <- as.numeric(preds)
  truth <- as.numeric(as.integer(truth))
  stopifnot(length(preds) == length(truth))
  n <- length(preds)
  if (n == 0L) return(numeric(0))
  if (n == 1L) return(truth)

  ord <- order(preds, seq_along(preds))
  y <- truth[ord]

  # PAVA: maintain blocks of (sum, count); merge while monotonicity violated.
  block_sum <- as.numeric(y)
  block_n   <- rep(1L, n)
  active    <- rep(TRUE, n)
  i <- 1L
  while (i < n) {
    if (!active[i]) { i <- i + 1L; next }
    j <- i + 1L
    while (j <= n && !active[j]) j <- j + 1L
    if (j > n) break
    mean_i <- block_sum[i] / block_n[i]
    mean_j <- block_sum[j] / block_n[j]
    if (mean_i > mean_j) {
      block_sum[i] <- block_sum[i] + block_sum[j]
      block_n[i]   <- block_n[i] + block_n[j]
      active[j] <- FALSE
      # back up to re-check left neighbour
      while (i > 1L && !active[i]) i <- i - 1L
      if (i > 1L) {
        prev <- i - 1L
        while (prev >= 1L && !active[prev]) prev <- prev - 1L
        if (prev >= 1L &&
            (block_sum[prev] / block_n[prev]) > (block_sum[i] / block_n[i])) {
          i <- prev
        }
      }
    } else {
      i <- j
    }
  }

  # Expand block means back to length n in sorted order
  cal_sorted <- numeric(n)
  cur_mean <- NA_real_
  for (k in seq_len(n)) {
    if (active[k]) cur_mean <- block_sum[k] / block_n[k]
    cal_sorted[k] <- cur_mean
  }

  # Map back to original input order
  out <- numeric(n)
  out[ord] <- cal_sorted
  out
}

#' Brier score (lower is better).
#' @param preds numeric in [0,1].
#' @param truth integer 0/1.
#' @return numeric scalar.
#' @export
brier_score <- function(preds, truth) {
  preds <- as.numeric(preds)
  truth <- as.numeric(truth)
  if (length(preds) == 0L) return(NA_real_)
  mean((preds - truth)^2, na.rm = TRUE)
}

#' Reliability diagram bins: equal-width on [0,1].
#'
#' @param preds numeric in [0,1].
#' @param truth integer 0/1.
#' @param n_bins integer.
#' @return data.frame with columns bin_lo, bin_hi, bin_mid, observed_rate,
#'   mean_pred, n. Empty bins return NA for observed_rate / mean_pred.
#' @export
reliability_diagram_data <- function(preds, truth, n_bins = 5L) {
  preds <- as.numeric(preds)
  truth <- as.integer(truth)
  edges <- seq(0, 1, length.out = n_bins + 1L)
  out <- data.frame(
    bin_lo = edges[-length(edges)],
    bin_hi = edges[-1L],
    bin_mid = (edges[-length(edges)] + edges[-1L]) / 2,
    observed_rate = NA_real_,
    mean_pred = NA_real_,
    n = 0L
  )
  for (i in seq_len(n_bins)) {
    in_bin <- if (i == n_bins) {
      preds >= out$bin_lo[i] & preds <= out$bin_hi[i]
    } else {
      preds >= out$bin_lo[i] & preds < out$bin_hi[i]
    }
    in_bin <- in_bin & !is.na(preds) & !is.na(truth)
    out$n[i] <- sum(in_bin)
    if (out$n[i] > 0L) {
      out$observed_rate[i] <- mean(truth[in_bin])
      out$mean_pred[i]     <- mean(preds[in_bin])
    }
  }
  out
}

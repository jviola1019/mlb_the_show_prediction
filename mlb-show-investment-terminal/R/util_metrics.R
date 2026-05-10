#' Small statistical helpers shared by tests + the OVERALL dashboard.
#'
#' Purposefully tiny — these are used both at runtime (server_overall.R)
#' and from tests (test-metrics.R), and must work without any extra deps
#' beyond `stats`.

#' Binary log loss with end-clipping to avoid `Inf` at p == 0 or 1.
#'
#' @param p numeric in [0, 1].
#' @param y integer 0/1.
#' @param eps numeric small clipping epsilon (default 1e-12).
#' @return numeric scalar mean log loss.
#' @export
log_loss <- function(p, y, eps = 1e-12) {
  p <- as.numeric(p)
  y <- as.numeric(y)
  if (length(p) == 0L || length(p) != length(y)) return(NA_real_)
  pc <- pmin(pmax(p, eps), 1 - eps)
  -mean(y * log(pc) + (1 - y) * log(1 - pc))
}

#' Wilson score interval for a binomial proportion.
#'
#' Closed-form, no normal approximation — appropriate for small `n` and for
#' rates near 0 or 1 (where Wald CI breaks down).
#'
#' @param k integer successes (>= 0).
#' @param n integer trials (>= 0).
#' @param conf numeric confidence level, default 0.90.
#' @return c(lo, hi). Returns c(NA, NA) when n == 0.
#' @export
wilson_ci <- function(k, n, conf = 0.90) {
  k <- as.integer(k); n <- as.integer(n)
  if (length(k) != 1L || length(n) != 1L || is.na(k) || is.na(n) || n <= 0L) {
    return(c(NA_real_, NA_real_))
  }
  if (k < 0L || k > n) return(c(NA_real_, NA_real_))
  alpha <- 1 - conf
  z <- stats::qnorm(1 - alpha / 2)
  phat <- k / n
  denom <- 1 + z^2 / n
  centre <- (phat + z^2 / (2 * n)) / denom
  spread <- (z * sqrt(phat * (1 - phat) / n + z^2 / (4 * n^2))) / denom
  c(max(0, centre - spread), min(1, centre + spread))
}

#' Directional hit rate with Wilson CI.
#'
#' A "hit" is `(p_up >= 0.5) == realized_up`. This is the rate the
#' walk-forward CV calls `hit_rate`; here we add a CI for the OVERALL
#' tab's app-health card.
#'
#' @param p_up numeric in [0, 1].
#' @param realized_up integer 0/1.
#' @param conf numeric confidence level, default 0.90.
#' @return list(rate, ci, n).
#' @export
directional_hit_rate <- function(p_up, realized_up, conf = 0.90) {
  p_up <- as.numeric(p_up); y <- as.integer(realized_up)
  n <- length(p_up)
  if (n == 0L || length(y) != n) {
    return(list(rate = NA_real_, ci = c(NA_real_, NA_real_), n = 0L))
  }
  hits <- (p_up >= 0.5) == (y == 1L)
  k <- sum(hits, na.rm = TRUE)
  list(rate = k / n, ci = wilson_ci(k, n, conf), n = n)
}

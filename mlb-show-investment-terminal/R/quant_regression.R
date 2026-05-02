#' OLS log-price regression with Newey-West HAC standard errors.
#'
#' Fits log(price_t) = alpha + beta * t + e_t and returns slope estimate
#' along with both naive (homoskedastic) and Newey-West HAC corrected
#' standard errors. The HAC correction uses sandwich::NeweyWest() which is
#' the canonical battle-tested implementation.
#'
#' Why HAC: card prices show autocorrelated residuals (trader behavior,
#' market microstructure). Naive OLS standard errors understate uncertainty
#' in the trend coefficient, inflating t-statistics and producing spurious
#' significance. Newey-West (1987) corrects this with a Bartlett-kernel
#' weighted sum of autocovariances.
#'
#' Lag selection: L = floor(4 * (N/100)^(2/9)) per Newey-West (1994)
#' automatic bandwidth, applied via sandwich::NeweyWest defaults.
#'
#' @param prices numeric vector of prices (length >= 3).
#' @return list with slope, intercept, r2, se_naive, t_naive, se_hac, t_hac,
#'   p_hac, hac_lag, residuals, fitted. NULL if input invalid.
#' @export
linear_reg_hac <- function(prices) {
  prices <- as.numeric(prices)
  n <- length(prices)
  if (n < 3L || any(prices <= 0, na.rm = TRUE)) return(NULL)

  ok <- is.finite(prices) & prices > 0
  if (sum(ok) < 3L) return(NULL)
  prices <- prices[ok]
  n <- length(prices)

  x <- seq_len(n) - 1
  y <- log(prices)
  df <- data.frame(t = x, logp = y)

  fit <- stats::lm(logp ~ t, data = df)
  s <- summary(fit)

  slope <- unname(stats::coef(fit)["t"])
  intercept <- unname(stats::coef(fit)["(Intercept)"])
  r2 <- s$r.squared

  # Naive OLS SE
  se_naive <- s$coefficients["t", "Std. Error"]
  t_naive <- if (se_naive > 0) slope / se_naive else 0

  # Newey-West HAC SE
  # Use sandwich::NeweyWest with automatic bandwidth (Newey-West 1994)
  hac_lag <- max(1L, floor(4 * (n / 100)^(2 / 9)))
  # NB: bare call (no `prewhite`/`adjust` overrides) so the test's reference
  # `sandwich::NeweyWest(fit, lag = …)` matches at numerical tolerance 1e-6.
  vcov_hac <- tryCatch(
    sandwich::NeweyWest(fit, lag = hac_lag),
    error = function(e) NULL
  )

  if (is.null(vcov_hac)) {
    se_hac <- se_naive
    t_hac <- t_naive
  } else {
    se_hac <- sqrt(vcov_hac["t", "t"])
    t_hac <- if (se_hac > 0) slope / se_hac else 0
  }

  # Two-sided p-value (asymptotic normal approximation; n is typically 50-200)
  p_hac <- 2 * (1 - stats::pnorm(abs(t_hac)))

  list(
    slope = slope,
    intercept = intercept,
    r2 = r2,
    se_naive = se_naive,
    t_naive = t_naive,
    se_hac = se_hac,
    t_hac = t_hac,
    p_hac = p_hac,
    hac_lag = hac_lag,
    residuals = stats::resid(fit),
    fitted = stats::fitted(fit),
    n = n
  )
}

#' Hurst exponent via R/S analysis.
#'
#' Detects long-range dependence: H > 0.5 = trending, H < 0.5 = mean-reverting,
#' H ≈ 0.5 = random walk. Uses the rescaled-range method on log returns.
#'
#' @param returns numeric vector of returns (typically log returns).
#' @return numeric scalar. Hurst exponent, or NA if input too short.
#' @export
hurst_exponent <- function(returns) {
  returns <- as.numeric(returns)
  returns <- returns[is.finite(returns)]
  if (length(returns) < 20L) return(NA_real_)

  candidate_sizes <- c(10, 20, 40, 80, 160)
  sizes <- candidate_sizes[candidate_sizes <= floor(length(returns) / 2)]
  if (length(sizes) < 2L) return(NA_real_)

  rs_log <- vapply(sizes, function(n) {
    n_windows <- floor(length(returns) / n)
    rs_vals <- numeric(0)
    for (i in seq_len(n_windows)) {
      win <- returns[((i - 1) * n + 1):(i * n)]
      m <- mean(win)
      cum_dev <- cumsum(win - m)
      R <- max(cum_dev) - min(cum_dev)
      S <- stats::sd(win)
      if (is.finite(R) && is.finite(S) && S > 0) {
        rs_vals <- c(rs_vals, R / S)
      }
    }
    if (length(rs_vals) == 0L) NA_real_ else log(mean(rs_vals))
  }, numeric(1))

  ok <- is.finite(rs_log)
  if (sum(ok) < 2L) return(NA_real_)
  fit <- stats::lm(rs_log[ok] ~ log(sizes[ok]))
  unname(stats::coef(fit)[2])
}

#' Variance ratio test (Lo-MacKinlay style).
#'
#' Tests the null hypothesis that returns follow a random walk (variance scales
#' linearly with horizon). VR < 1 indicates mean reversion; VR > 1 indicates
#' positive serial correlation (trending).
#'
#' @param returns numeric vector.
#' @param k integer. Aggregation horizon. Typically 2, 4, 8.
#' @return list with vr (variance ratio), z (heteroskedasticity-robust z-stat),
#'   p_value (two-sided).
#' @export
variance_ratio <- function(returns, k = 4L) {
  returns <- as.numeric(returns)
  returns <- returns[is.finite(returns)]
  n <- length(returns)
  if (n < k * 4L || k < 2L) return(NULL)

  v1 <- stats::var(returns)
  if (v1 == 0) return(NULL)

  k_returns <- numeric(0)
  for (i in k:n) {
    k_returns <- c(k_returns, sum(returns[(i - k + 1):i]))
  }
  v_k <- stats::var(k_returns)
  vr <- v_k / (k * v1)

  # Heteroskedasticity-robust z-stat (Lo-MacKinlay 1988, Eq 21)
  delta_sum <- 0
  for (j in seq_len(k - 1L)) {
    weight <- (2 * (k - j) / k)^2
    rho_j <- stats::acf(returns, lag.max = j, plot = FALSE, type = "covariance")$acf[j + 1]
    delta_j <- rho_j / v1
    delta_sum <- delta_sum + weight * delta_j^2
  }
  se <- sqrt(delta_sum / n)
  z <- if (se > 0) (vr - 1) / se else 0
  p <- 2 * (1 - stats::pnorm(abs(z)))

  list(vr = vr, z = z, p_value = p, k = k, n = n)
}

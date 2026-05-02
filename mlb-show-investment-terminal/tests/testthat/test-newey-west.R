test_that("HAC SE inflated vs naive on AR(1) residuals", {
  set.seed(99)
  n <- 200
  x <- 1:n
  resid <- as.numeric(arima.sim(list(ar = 0.7), n = n, sd = 0.5))
  y <- 0.005 * x + resid
  prices <- exp(y)
  fit <- linear_reg_hac(prices)
  expect_gt(fit$se_hac / fit$se_naive, 1.5)
  expect_lt(abs(fit$t_hac), abs(fit$t_naive))
})

test_that("HAC matches sandwich::NeweyWest reference call", {
  set.seed(42)
  n <- 100
  x <- 1:n
  y <- 0.001 * x + rnorm(n, sd = 0.1)
  prices <- exp(y)
  ref_fit <- stats::lm(y ~ x)
  ref_se <- sqrt(sandwich::NeweyWest(ref_fit, lag = floor(4 * (n / 100)^(2/9)))[2, 2])
  ours <- linear_reg_hac(prices)
  expect_equal(ours$se_hac, ref_se, tolerance = 1e-6)
})

test_that("linear_reg_hac returns NULL on degenerate input", {
  expect_null(linear_reg_hac(c(100, 100)))
  expect_null(linear_reg_hac(c(-1, -2, -3)))
  expect_null(linear_reg_hac(numeric(0)))
})

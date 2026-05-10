# Phase H: bootstrap reproducibility + temporal-dependence respect.

test_that("block_bootstrap is reproducible under set.seed", {
  rets <- rnorm(100, sd = 0.01)  # any returns vector
  set.seed(42)
  fc1 <- block_bootstrap(rets, current = 1000, horizon = 5, n_sims = 200)
  set.seed(42)
  fc2 <- block_bootstrap(rets, current = 1000, horizon = 5, n_sims = 200)
  expect_equal(fc1$paths, fc2$paths)
  expect_equal(fc1$summary, fc2$summary)
})

test_that("walk_forward_cv is reproducible under set.seed", {
  set.seed(7)
  prices <- exp(cumsum(c(log(1000), rnorm(120, 0, 0.01))))
  set.seed(99)
  w1 <- walk_forward_cv(prices, horizon = 3, lookback = 30,
                        n_sims_per = 100, boot_b = 200,
                        ci_method = "per_trade")
  set.seed(99)
  w2 <- walk_forward_cv(prices, horizon = 3, lookback = 30,
                        n_sims_per = 100, boot_b = 200,
                        ci_method = "per_trade")
  expect_equal(w1$brier_ci, w2$brier_ci)
  expect_equal(w1$ic_ci, w2$ic_ci)
  expect_equal(w1$n_trades, w2$n_trades)
})

test_that("block bootstrap CI is wider than iid on AR(1) returns", {
  # On strongly autocorrelated returns, ignoring temporal dependence
  # under-estimates uncertainty. The block bootstrap must produce a
  # WIDER CI than naive iid.
  skip_on_cran()
  set.seed(11)
  rets <- as.numeric(arima.sim(list(ar = 0.7), n = 300, sd = 0.01))
  prices <- exp(cumsum(c(log(1000), rets)))
  set.seed(1)
  wb <- walk_forward_cv(prices, horizon = 5, lookback = 50,
                        n_sims_per = 200, boot_b = 500,
                        ci_method = "block")
  set.seed(1)
  wp <- walk_forward_cv(prices, horizon = 5, lookback = 50,
                        n_sims_per = 200, boot_b = 500,
                        ci_method = "per_trade")
  block_w <- diff(wb$brier_ci)
  iid_w   <- diff(wp$brier_ci)
  expect_gt(block_w, iid_w)
})

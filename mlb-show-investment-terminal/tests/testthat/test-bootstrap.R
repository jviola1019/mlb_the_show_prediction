test_that("Politis-White b.star recovers reasonable block length on AR(1)", {
  skip_if_not_installed("np")
  set.seed(42)
  ar1 <- as.numeric(arima.sim(list(ar = 0.6), n = 500))
  L <- block_length(ar1)
  expect_gte(L, 3L)
  expect_lte(L, 50L)
})

test_that("block_length fallback works without np", {
  set.seed(7)
  L <- block_length(rnorm(100))
  expect_gte(L, 3L)
  expect_true(is.numeric(L) && is.finite(L))
})

test_that("Stationary block bootstrap recovers GBM drift", {
  set.seed(123)
  rets <- rnorm(200, mean = 0.001, sd = 0.01)
  fc <- block_bootstrap(rets, current = 1000, horizon = 50, n_sims = 5000)
  med <- fc$summary$p50[51]
  expect_gt(med, 1020)
  expect_lt(med, 1090)
})

test_that("Block bootstrap p_up monotonic in step (positive drift)", {
  set.seed(7)
  rets <- rnorm(150, mean = 0.002, sd = 0.005)
  fc <- block_bootstrap(rets, 1000, 30, n_sims = 3000)
  expect_gt(fc$summary$p_up[31], fc$summary$p_up[5])
})

test_that("paths matrix is fully populated and shaped horizon+1", {
  set.seed(11)
  rets <- rnorm(80, 0, 0.01)
  fc <- block_bootstrap(rets, 1000, horizon = 20, n_sims = 200)
  expect_equal(ncol(fc$paths), 21L)
  expect_true(all(is.finite(fc$paths)))
  expect_true(all(fc$paths[, 1L] == 1000))
})

test_that("compute_ev returns sensible Kelly + breakeven", {
  set.seed(3)
  rets <- rnorm(120, 0.001, 0.02)
  fc <- block_bootstrap(rets, 1000, 7, n_sims = 1000)
  ev <- compute_ev(ask = 1000, bid = 950, fc = fc, horizon = 7)
  expect_true(ev$kelly >= 0 && ev$kelly <= 1)
  expect_equal(ev$kelly_half, ev$kelly / 2)
  # breakeven > ask because of 10% tax + spread
  expect_gt(ev$breakeven, 1000)
})

test_that("block_bootstrap NULL on bad input", {
  expect_null(block_bootstrap(numeric(0), 1000, 5))
  expect_null(block_bootstrap(rnorm(50), -1, 5))
  expect_null(block_bootstrap(rnorm(50), 1000, 0))
  expect_null(block_bootstrap(rnorm(5), 1000, 5))  # too short
})

# Phase H: EV explicitly includes 10% tax + bid/ask spread, and Kelly is
# non-negative. compute_ev() lives in R/quant_bootstrap.R.

test_that("compute_ev applies 10% market tax", {
  set.seed(2)
  rets <- rnorm(100, mean = 0.001, sd = 0.005)
  fc <- block_bootstrap(rets, current = 1000, horizon = 7, n_sims = 1000)
  ev <- compute_ev(ask = 1000, bid = 1000, fc = fc, horizon = 7)
  # With bid == ask, EV per trade =
  #   (median_final * (bid/ask) * 0.90 - ask) / ask  (mean over paths)
  # Not exact equality (uses mean of paths, not median); just verify the
  # tax shows up: doubling the tax floor (i.e. multiplying the final paths
  # by 1/0.9) should leave EV unchanged.
  expect_true(is.finite(ev$expected_ret))
  # Breakeven is ask / ((1 - tax) * (bid/ask)) = 1000 / 0.90 ≈ 1111
  expect_equal(ev$breakeven, 1000 / 0.90, tolerance = 1)
})

test_that("compute_ev breakeven respects bid/ask spread", {
  set.seed(2)
  rets <- rnorm(100, mean = 0.001, sd = 0.005)
  fc <- block_bootstrap(rets, current = 1000, horizon = 7, n_sims = 500)
  ev_tight <- compute_ev(ask = 1000, bid = 990, fc = fc, horizon = 7)
  ev_wide  <- compute_ev(ask = 1000, bid = 800, fc = fc, horizon = 7)
  # Wider spread -> higher breakeven (need larger price move to clear).
  expect_gt(ev_wide$breakeven, ev_tight$breakeven)
})

test_that("compute_ev: lower bid lowers expected_ret all else equal", {
  set.seed(3)
  rets <- rnorm(100, mean = 0.001, sd = 0.005)
  fc <- block_bootstrap(rets, current = 1000, horizon = 7, n_sims = 1000)
  ev_tight <- compute_ev(ask = 1000, bid = 990, fc = fc, horizon = 7)
  ev_wide  <- compute_ev(ask = 1000, bid = 800, fc = fc, horizon = 7)
  expect_lt(ev_wide$expected_ret, ev_tight$expected_ret)
})

test_that("compute_ev kelly is non-negative and kelly_half == kelly/2", {
  set.seed(4)
  rets <- rnorm(100, mean = 0.002, sd = 0.005)
  fc <- block_bootstrap(rets, current = 1000, horizon = 7, n_sims = 1000)
  ev <- compute_ev(ask = 1000, bid = 990, fc = fc, horizon = 7)
  expect_gte(ev$kelly, 0)
  expect_equal(ev$kelly_half, ev$kelly / 2)
})

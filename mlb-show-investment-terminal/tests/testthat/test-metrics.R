# Phase H: util_metrics.R — log_loss, wilson_ci, directional_hit_rate.

test_that("log_loss matches closed-form binary cross-entropy", {
  # y=1, p=0.5 -> -log(0.5) = 0.6931472
  expect_equal(log_loss(0.5, 1), -log(0.5), tolerance = 1e-9)
  # y=0, p=0.5 -> -log(0.5)
  expect_equal(log_loss(0.5, 0), -log(0.5), tolerance = 1e-9)
  # y=1, p=0.99 -> -log(0.99)
  expect_equal(log_loss(0.99, 1), -log(0.99), tolerance = 1e-9)
  # y=0, p=0.01 -> -log(0.99)
  expect_equal(log_loss(0.01, 0), -log(0.99), tolerance = 1e-9)
  # vector mean
  expect_equal(log_loss(c(0.5, 0.5), c(1, 0)), -log(0.5), tolerance = 1e-9)
})

test_that("log_loss clipping prevents Inf at p == 0 or p == 1", {
  expect_true(is.finite(log_loss(0, 1)))
  expect_true(is.finite(log_loss(1, 0)))
  # The clipped result is bounded above by -log(eps).
  expect_lt(log_loss(0, 1), 30)
  expect_lt(log_loss(1, 0), 30)
})

test_that("wilson_ci endpoints behave at extremes", {
  ci0 <- wilson_ci(0, 10, conf = 0.90)
  expect_equal(ci0[1], 0)
  expect_gt(ci0[2], 0.10); expect_lt(ci0[2], 0.40)
  ci1 <- wilson_ci(10, 10, conf = 0.90)
  expect_equal(ci1[2], 1)
  expect_gt(ci1[1], 0.60); expect_lt(ci1[1], 0.90)
  expect_equal(wilson_ci(0, 0), c(NA_real_, NA_real_))
})

test_that("wilson_ci width shrinks monotonically with n", {
  w_small <- diff(wilson_ci(5, 10))
  w_med   <- diff(wilson_ci(50, 100))
  w_large <- diff(wilson_ci(500, 1000))
  expect_gt(w_small, w_med)
  expect_gt(w_med,   w_large)
})

test_that("directional_hit_rate matches manual calc + wilson", {
  set.seed(7)
  p_up <- runif(50)
  y    <- rbinom(50, 1, 0.5)
  out  <- directional_hit_rate(p_up, y)
  expect_equal(out$rate, mean((p_up >= 0.5) == (y == 1L)))
  expect_equal(out$ci, wilson_ci(round(out$rate * 50), 50))
})

test_that("directional_hit_rate handles empty input", {
  out <- directional_hit_rate(numeric(0), integer(0))
  expect_true(is.na(out$rate))
  expect_equal(out$ci, c(NA_real_, NA_real_))
  expect_equal(out$n, 0L)
})

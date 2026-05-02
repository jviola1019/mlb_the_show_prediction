test_that("probably::cal_estimate_isotonic matches custom PAV", {
  skip_if_not_installed("probably")
  set.seed(55)
  n <- 200
  truth <- rbinom(n, 1, 0.3)
  miscal <- pmax(0.01, pmin(0.99, truth * 0.5 + rnorm(n, 0, 0.2) + 0.3))
  prob_cal <- isotonic_via_probably(miscal, truth)
  custom_cal <- isotonic_pav_custom(miscal, truth)
  expect_equal(prob_cal, custom_cal, tolerance = 1e-6)
})

test_that("Isotonic output is monotonically non-decreasing", {
  set.seed(1)
  n <- 100
  preds <- runif(n)
  truth <- rbinom(n, 1, preds)
  cal <- isotonic_pav_custom(preds, truth)
  ord <- order(preds)
  expect_true(all(diff(cal[ord]) >= -1e-9))
})

test_that("Isotonic improves Brier on miscalibrated input", {
  set.seed(3)
  n <- 500
  truth <- rbinom(n, 1, 0.4)
  bad <- ifelse(truth == 1, 0.95, 0.05)  # over-confident
  cal <- isotonic_pav_custom(bad, truth)
  expect_lte(brier_score(cal, truth), brier_score(bad, truth))
})

test_that("PAV handles edge cases", {
  expect_equal(isotonic_pav_custom(numeric(0), integer(0)), numeric(0))
  expect_equal(length(isotonic_pav_custom(0.5, 1L)), 1L)
  # All zeros / all ones — no violations, output identical to truth
  preds <- c(0.1, 0.5, 0.9)
  expect_equal(isotonic_pav_custom(preds, c(0, 0, 0)), c(0, 0, 0))
  expect_equal(isotonic_pav_custom(preds, c(1, 1, 1)), c(1, 1, 1))
})

test_that("reliability_diagram_data returns 5 bins by default", {
  set.seed(8)
  preds <- runif(200)
  truth <- rbinom(200, 1, preds)
  rd <- reliability_diagram_data(preds, truth)
  expect_equal(nrow(rd), 5L)
  expect_equal(rd$bin_lo, c(0, 0.2, 0.4, 0.6, 0.8))
  expect_equal(rd$bin_hi, c(0.2, 0.4, 0.6, 0.8, 1))
  expect_true(all(rd$n > 0))
})

test_that("brier_score basics", {
  expect_equal(brier_score(c(1, 0, 1), c(1, 0, 1)), 0)
  expect_equal(brier_score(c(0.5, 0.5), c(0, 1)), 0.25)
  expect_true(is.na(brier_score(numeric(0), integer(0))))
})

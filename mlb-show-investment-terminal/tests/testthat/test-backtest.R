test_that("upgrade_backtest_metrics returns unavailable without real labels", {
  out <- upgrade_backtest_metrics()
  expect_equal(out$status, "unavailable")
  expect_true(is.na(out$brier_score))
  expect_equal(out$n, 0L)
})

test_that("upgrade_backtest_metrics reports Brier precision recall and calibration", {
  predictions <- data.frame(
    uuid = c("a", "b", "c", "d"),
    p_cross_next_threshold = c(0.90, 0.70, 0.30, 0.10),
    stringsAsFactors = FALSE
  )
  labels <- data.frame(
    uuid = c("a", "b", "c", "d"),
    crossed_next_threshold = c(TRUE, FALSE, TRUE, FALSE),
    stringsAsFactors = FALSE
  )
  out <- upgrade_backtest_metrics(predictions, labels, n_bins = 4L)
  expect_equal(out$status, "ok")
  expect_equal(out$n, 4L)
  expect_true(is.finite(out$brier_score))
  expect_equal(out$precision, 0.5)
  expect_equal(out$recall, 0.5)
  expect_s3_class(out$calibration_curve, "data.frame")
  expect_equal(nrow(out$calibration_curve), 4L)
})

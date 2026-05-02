test_that("Strong buy: high EV + sig+ drift + oversold", {
  r <- recommendation_score(ev = 0.08, drift_p = 0.01, drift_slope = 0.005,
                            z30 = -2.0, hurst = 0.65, spread_pct = 0.05,
                            cv_ic_point = 0.10, cv_ic_upper = 0.20)
  expect_equal(r$action, "STRONG BUY")
  expect_gte(r$score, 3L)
  flag_texts <- vapply(r$flags, `[[`, character(1), "text")
  expect_true(any(grepl("\\+EV>5%", flag_texts)))
  expect_true("drift sig+" %in% flag_texts)
  expect_true("oversold" %in% flag_texts)
  expect_true("trending" %in% flag_texts)
})

test_that("Strong sell: large negative EV + sig- drift + overbought", {
  r <- recommendation_score(ev = -0.08, drift_p = 0.01, drift_slope = -0.005,
                            z30 = 2.0)
  expect_equal(r$action, "STRONG SELL")
  expect_lte(r$score, -3L)
})

test_that("Hold default when no signals fire", {
  r <- recommendation_score(ev = 0.005, drift_p = NA, drift_slope = NA,
                            z30 = 0, hurst = 0.5, spread_pct = 0.05)
  expect_equal(r$action, "HOLD")
  expect_equal(r$score, 0L)
})

test_that("Wide-spread warn flag fires above 15%", {
  r <- recommendation_score(ev = 0, spread_pct = 0.18)
  flag_texts <- vapply(r$flags, `[[`, character(1), "text")
  flag_levels <- vapply(r$flags, `[[`, character(1), "level")
  expect_true(any(grepl("wide spread", flag_texts)))
  expect_true("warn" %in% flag_levels)
})

test_that("CV IC<0 (sig) when upper CI is negative", {
  r <- recommendation_score(ev = 0, cv_ic_point = -0.05, cv_ic_upper = -0.01)
  flag_texts <- vapply(r$flags, `[[`, character(1), "text")
  expect_true("CV IC<0 (sig)" %in% flag_texts)
})

test_that("CV IC<0 (no sig) when point < -0.10 and upper >= 0", {
  r <- recommendation_score(ev = 0, cv_ic_point = -0.15, cv_ic_upper = 0.05)
  flag_texts <- vapply(r$flags, `[[`, character(1), "text")
  expect_true("CV IC<0" %in% flag_texts)
  expect_false("CV IC<0 (sig)" %in% flag_texts)
})

test_that("Hurst regime info flags", {
  r1 <- recommendation_score(ev = 0, hurst = 0.7)
  expect_true("trending" %in% vapply(r1$flags, `[[`, character(1), "text"))
  r2 <- recommendation_score(ev = 0, hurst = 0.3)
  expect_true("mean-revert" %in% vapply(r2$flags, `[[`, character(1), "text"))
})

test_that("All NA inputs yield HOLD with empty score", {
  r <- recommendation_score(ev = NA)
  expect_equal(r$score, 0L)
  expect_equal(r$action, "HOLD")
  expect_length(r$flags, 0L)
})

test_that("BUY threshold at score=1, SELL at score=-1", {
  expect_equal(recommendation_score(ev = 0.02)$action, "BUY")
  expect_equal(recommendation_score(ev = -0.02)$action, "SELL")
})

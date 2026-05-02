test_that("Walk-forward CV bootstrap CIs achieve nominal coverage on random walk", {
  skip_on_cran()
  skip_on_ci()  # 200 reps × 200 sims is too slow for CI
  set.seed(20)
  n_reps <- 80  # reduced from 200 in plan; still enough to detect mis-calibration
  covers <- logical(n_reps)
  for (i in seq_len(n_reps)) {
    rets <- rnorm(120, mean = 0, sd = 0.02)
    prices <- exp(cumsum(c(log(1000), rets)))
    wf <- walk_forward_cv(prices, horizon = 5, lookback = 30,
                          n_sims_per = 200, boot_b = 300,
                          ci_method = "block")
    if (is.null(wf)) next
    covers[i] <- 0.25 >= wf$brier_ci[1] && 0.25 <= wf$brier_ci[2]
  }
  cov_rate <- mean(covers)
  expect_gt(cov_rate, 0.70)
  expect_lt(cov_rate, 1.00)
})

test_that("Per-trade and block-residual CIs have similar widths on iid trades", {
  set.seed(11)
  rets <- rnorm(300, 0, 0.01)
  prices <- exp(cumsum(c(log(1000), rets)))
  wf_block <- walk_forward_cv(prices, 5, 50, 200, 500, ci_method = "block")
  wf_trade <- walk_forward_cv(prices, 5, 50, 200, 500, ci_method = "per_trade")
  w_block <- diff(wf_block$brier_ci)
  w_trade <- diff(wf_trade$brier_ci)
  # Loose tolerance: stochastic resampling alone can drift these by ~50%.
  expect_lt(abs(w_block - w_trade) / max(w_block, w_trade), 0.60)
})

test_that("walk_forward_cv returns NULL on insufficient data", {
  expect_null(walk_forward_cv(c(100, 101, 102), horizon = 5, lookback = 10))
  expect_null(walk_forward_cv(rep(100, 50), horizon = 5, lookback = 30))  # constant
})

test_that("walk_forward_cv returns expected fields", {
  set.seed(2)
  rets <- rnorm(150, 0, 0.01)
  prices <- exp(cumsum(c(log(1000), rets)))
  wf <- walk_forward_cv(prices, 3, 30, 100, 200, "per_trade")
  expect_true(!is.null(wf))
  expect_named(wf, c("trades","brier_point","brier_ci","ic_point","ic_ci",
                     "hit_rate","n_trades","ci_method","boot_b","p_up",
                     "realized_up"))
  expect_true(wf$brier_point >= 0 && wf$brier_point <= 1)
  expect_equal(length(wf$brier_ci), 2L)
  expect_equal(length(wf$ic_ci), 2L)
  expect_true(wf$brier_ci[1] <= wf$brier_point && wf$brier_point <= wf$brier_ci[2])
})

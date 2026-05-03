make_listing <- function(uuid = "abcdef0123456789abcdef0123456789",
                         ask = 100, bid = 90, n_orders = 50L) {
  list(
    item = list(uuid = uuid, name = "X", rarity = "Diamond"),
    best_sell_price = ask,
    best_buy_price = bid,
    completed_orders = lapply(seq_len(n_orders), function(i)
      list(date = "05/02/2026 12:00:00", price = "100"))
  )
}
make_ph <- function(n = 100, max_age_h = 1) {
  now <- Sys.time()
  data.frame(
    timestamp = seq(now - 3600 * max_age_h * (n - 1) / n,
                    now - 3600 * max_age_h, length.out = n),
    price = exp(cumsum(c(log(100), rnorm(n - 1, 0, 0.01))))
  )
}
make_wfcv <- function(n_trades = 50L,
                      ic_point = 0.10, ic_ci = c(0.02, 0.18),
                      brier_point = 0.22, brier_ci = c(0.18, 0.27)) {
  list(n_trades = n_trades, ic_point = ic_point, ic_ci = ic_ci,
       brier_point = brier_point, brier_ci = brier_ci,
       hit_rate = 0.55, ci_method = "block", boot_b = 500,
       trades = data.frame(p_up = runif(n_trades), realized_up = 0L,
                           brier_t = rep(0.22, n_trades)))
}

test_that("All 6 gates pass -> INVESTABLE", {
  set.seed(1)
  g <- validation_gates(make_ph(100, 1), make_listing(), make_wfcv(),
                        horizon = 7L)
  v <- gating_verdict(g)
  expect_equal(v$status, "INVESTABLE")
  expect_length(v$failed, 0L)
})

test_that("Gate 1 (schema) fails when uuid invalid", {
  set.seed(2)
  bad <- make_listing(uuid = "not-a-uuid")
  g <- validation_gates(make_ph(100, 1), bad, make_wfcv(), horizon = 7L)
  expect_false(g$schema_valid$passed)
  v <- gating_verdict(g)
  expect_equal(v$status, "NOT INVESTABLE")
})

test_that("Gate 1 (schema) fails when completed_orders < 8", {
  set.seed(3)
  bad <- make_listing(n_orders = 5L)
  g <- validation_gates(make_ph(100, 1), bad, make_wfcv(), horizon = 7L)
  expect_false(g$schema_valid$passed)
})

test_that("Gate 2 (history) fails when nrow < 6*horizon", {
  set.seed(4)
  small <- data.frame(timestamp = Sys.time() - seq(0, 30 * 60, by = 60),
                      price = rep(100, 31))
  g <- validation_gates(small, make_listing(), make_wfcv(), horizon = 7L)
  expect_false(g$history_sufficient$passed)
  v <- gating_verdict(g)
  expect_equal(v$status, "NOT INVESTABLE")
})

test_that("Gate 3 (freshness) fails for stale data", {
  set.seed(5)
  ph <- make_ph(100, max_age_h = 100)  # >48h old
  g <- validation_gates(ph, make_listing(), make_wfcv(), horizon = 7L)
  expect_false(g$data_fresh$passed)
})

test_that("Gate 4 (cv_available) fails when wfcv is NULL", {
  set.seed(6)
  g <- validation_gates(make_ph(100, 1), make_listing(), NULL, horizon = 7L)
  expect_false(g$cv_available$passed)
  v <- gating_verdict(g)
  expect_equal(v$status, "NOT INVESTABLE")
})

test_that("Gate 5 (skill) fails when IC upper bound < 0 -> OBSERVATIONAL", {
  set.seed(7)
  bad_skill <- make_wfcv(ic_point = -0.20, ic_ci = c(-0.30, -0.10))
  g <- validation_gates(make_ph(100, 1), make_listing(), bad_skill,
                        horizon = 7L)
  expect_false(g$cv_skill_not_negative_sig$passed)
  v <- gating_verdict(g)
  expect_equal(v$status, "OBSERVATIONAL ONLY")
  expect_true(any(grepl("upper bound", v$reasons)))
})

test_that("Gate 6 (CI width) fails when IC width > 0.50 -> OBSERVATIONAL", {
  set.seed(8)
  wide_ci <- make_wfcv(ic_ci = c(-0.30, 0.40))  # width 0.70
  g <- validation_gates(make_ph(100, 1), make_listing(), wide_ci,
                        horizon = 7L)
  expect_false(g$ci_width_acceptable$passed)
  v <- gating_verdict(g)
  expect_equal(v$status, "OBSERVATIONAL ONLY")
})

test_that("gates_summary_pills renders 6 rows + reason text on failures", {
  set.seed(9)
  g <- validation_gates(make_ph(20, 1), make_listing(n_orders = 5L),
                        NULL, horizon = 7L)
  out <- gates_summary_pills(g)
  html <- as.character(htmltools::renderTags(out)$html)
  expect_true(grepl("SCHEMA", html))
  expect_true(grepl("HISTORY", html))
  expect_true(grepl("✗", html))  # at least one fail mark
  expect_true(grepl("gate-reason", html))
})

test_that("gating_verdict reasons are non-empty when gates fail", {
  set.seed(10)
  g <- validation_gates(make_ph(20, 1), make_listing(), NULL, horizon = 7L)
  v <- gating_verdict(g)
  expect_gt(length(v$reasons), 0L)
  expect_true(all(nchar(v$reasons) > 0L))
})

# Phase H: tier_grade boundaries.
# Builds synthetic verdict + gate inputs (these are NOT user-facing data —
# they live entirely under tests/ and are never reachable from the app's
# runtime path; per the no-synthetic-data rule they're test fixtures only).

.gates_all_pass <- function() {
  list(
    schema_valid              = list(passed = TRUE, reason = "ok"),
    history_sufficient        = list(passed = TRUE, reason = "ok"),
    data_fresh                = list(passed = TRUE, reason = "ok"),
    cv_available              = list(passed = TRUE, reason = "ok"),
    cv_skill_not_negative_sig = list(passed = TRUE, reason = "ok"),
    ci_width_acceptable       = list(passed = TRUE, reason = "ok"),
    calibration_present       = list(passed = TRUE, reason = "ok")
  )
}

.investable_v <- list(status = "INVESTABLE", failed = character(0),
                     reasons = character(0))
.observ_v     <- list(status = "OBSERVATIONAL ONLY",
                      failed = c("cv_skill_not_negative_sig"),
                      reasons = c("CV IC upper bound negative"))
.notinv_schema <- list(status = "NOT INVESTABLE",
                       failed = c("schema_valid"),
                       reasons = c("schema fail"))
.notinv_fresh <- list(status = "NOT INVESTABLE",
                      failed = c("data_fresh"),
                      reasons = c("48h+"))
.notinv_thin <- list(status = "NOT INVESTABLE",
                     failed = c("history_sufficient", "cv_available"),
                     reasons = c("only 30 points", "wfcv NULL"))

.diamond_wfcv <- list(ic_ci  = c(0.06, 0.20),
                      brier_ci = c(0.20, 0.28))  # width 0.08

test_that("DIAMOND when all five DIAMOND criteria meet exactly", {
  t <- tier_grade(.investable_v, .gates_all_pass(),
                  liquidity_score = 0.75,
                  wfcv = .diamond_wfcv,
                  holdout_brier_delta = -0.010)
  expect_equal(t$tier, "DIAMOND")
  expect_match(t$reason, "IC lower CI=0.06")
})

test_that("DIAMOND degrades to GOLD when any single criterion fails", {
  # Liquidity below 0.7
  t1 <- tier_grade(.investable_v, .gates_all_pass(),
                   liquidity_score = 0.65,
                   wfcv = .diamond_wfcv,
                   holdout_brier_delta = -0.010)
  expect_equal(t1$tier, "GOLD")

  # IC lower CI just below 0.05
  bad_wfcv <- list(ic_ci = c(0.04, 0.20), brier_ci = c(0.20, 0.28))
  t2 <- tier_grade(.investable_v, .gates_all_pass(),
                   liquidity_score = 0.80,
                   wfcv = bad_wfcv,
                   holdout_brier_delta = -0.010)
  expect_equal(t2$tier, "GOLD")

  # Brier CI width too wide
  wide_wfcv <- list(ic_ci = c(0.06, 0.20), brier_ci = c(0.20, 0.35))
  t3 <- tier_grade(.investable_v, .gates_all_pass(),
                   liquidity_score = 0.80,
                   wfcv = wide_wfcv,
                   holdout_brier_delta = -0.010)
  expect_equal(t3$tier, "GOLD")

  # Calibration improvement too small
  t4 <- tier_grade(.investable_v, .gates_all_pass(),
                   liquidity_score = 0.80,
                   wfcv = .diamond_wfcv,
                   holdout_brier_delta = -0.001)
  expect_equal(t4$tier, "GOLD")
})

test_that("SILVER iff verdict OBSERVATIONAL ONLY", {
  t <- tier_grade(.observ_v, .gates_all_pass(),
                  liquidity_score = 0.9,
                  wfcv = .diamond_wfcv,
                  holdout_brier_delta = -0.010)
  expect_equal(t$tier, "SILVER")
})

test_that("BRONZE when only thin-data gates fail (history/cv)", {
  thin_gates <- .gates_all_pass()
  thin_gates$history_sufficient <- list(passed = FALSE,
                                        reason = "only 30 points")
  thin_gates$cv_available <- list(passed = FALSE, reason = "wfcv NULL")
  t <- tier_grade(.notinv_thin, thin_gates,
                  liquidity_score = 0.5,
                  wfcv = NULL,
                  holdout_brier_delta = NA_real_)
  expect_equal(t$tier, "BRONZE")
  expect_match(t$reason, "data sparse")
})

test_that("ABSTAIN when schema_valid failed", {
  bad_gates <- .gates_all_pass()
  bad_gates$schema_valid <- list(passed = FALSE, reason = "missing UUID")
  t <- tier_grade(.notinv_schema, bad_gates,
                  liquidity_score = 0,
                  wfcv = NULL,
                  holdout_brier_delta = NA_real_)
  expect_equal(t$tier, "ABSTAIN")
  expect_match(t$reason, "hard data-quality block")
})

test_that("ABSTAIN when data_fresh failed", {
  stale_gates <- .gates_all_pass()
  stale_gates$data_fresh <- list(passed = FALSE, reason = "48h stale")
  t <- tier_grade(.notinv_fresh, stale_gates,
                  liquidity_score = 0.5,
                  wfcv = .diamond_wfcv,
                  holdout_brier_delta = -0.010)
  expect_equal(t$tier, "ABSTAIN")
})

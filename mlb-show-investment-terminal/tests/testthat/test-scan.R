make_listing_full <- function(uuid, name = "X", rarity = "Diamond",
                              ovr = 90L, ask = 100, bid = 90,
                              n_orders = 60L, n_history = 100L) {
  list(
    listing_name = name,
    best_sell_price = ask, best_buy_price = bid,
    item = list(uuid = uuid, name = name, rarity = rarity, ovr = ovr,
                team = "X"),
    completed_orders = lapply(seq_len(n_orders), function(i)
      list(date = format(Sys.time() - i * 60, "%m/%d/%Y %H:%M:%S"),
           price = sprintf("%d", as.integer(ask) + i %% 5))),
    price_history = list()
  )
}

test_that("scan_partition splits into BUY/SELL/OBSERVE/DROPPED correctly", {
  df <- data.frame(
    uuid = c(strrep("a", 32), strrep("b", 32), strrep("c", 32),
             strrep("d", 32)),
    name = c("Buyish","Sellish","Observe","Drop"),
    rarity = "Diamond",
    ovr = 90L, team = "X",
    ask = c(100, 100, 100, 100), bid = c(90, 90, 90, 90),
    spread_pct = 0.10,
    ev_7d   = c(0.08, -0.07, 0.02, NA_real_),
    p_up_7d = c(0.6, 0.4, 0.5, NA_real_),
    score   = c(2L, -2L, 0L, NA_integer_),
    action  = c("BUY","SELL","OBSERVE","ABSTAIN"),
    direction = c("▲","▼","—","—"),
    verdict_status = c("INVESTABLE","INVESTABLE","OBSERVATIONAL ONLY",
                       "NOT INVESTABLE"),
    gates_failed_csv = c("","",
                         "ci_width_acceptable",
                         "history_sufficient,cv_available"),
    n_trades = c(40L, 40L, 40L, 0L),
    ic_point = c(0.10, 0.10, 0.05, NA_real_),
    ic_ci_lo = c(0.02, 0.02, -0.05, NA_real_),
    ic_ci_hi = c(0.18, 0.18, 0.40,  NA_real_),
    stringsAsFactors = FALSE
  )
  p <- scan_partition(df)
  expect_equal(nrow(p$buy), 1L); expect_equal(p$buy$name, "Buyish")
  expect_equal(nrow(p$sell), 1L); expect_equal(p$sell$name, "Sellish")
  expect_equal(nrow(p$observe), 1L); expect_equal(p$observe$name, "Observe")
  expect_equal(nrow(p$dropped), 1L); expect_equal(p$dropped$name, "Drop")
})

test_that("scan_partition orders BUY by score desc then EV desc", {
  df <- data.frame(
    uuid = vapply(letters[1:3], function(c) strrep(c, 32), character(1)),
    name = c("A","B","C"),
    rarity = "Diamond", ovr = 90L, team = "X",
    ask = 100, bid = 90, spread_pct = 0.10,
    ev_7d = c(0.05, 0.10, 0.20),
    p_up_7d = 0.6,
    score = c(3L, 1L, 1L),
    action = c("STRONG BUY","BUY","BUY"),
    direction = "▲",
    verdict_status = "INVESTABLE",
    gates_failed_csv = "",
    n_trades = 40L, ic_point = 0.1, ic_ci_lo = 0.02, ic_ci_hi = 0.18,
    stringsAsFactors = FALSE
  )
  p <- scan_partition(df)
  expect_equal(p$buy$name, c("A","C","B"))  # 3 then ties 1+1 broken by ev
})

test_that("scan_partition separates flip buys upgrade buys holds sells invalid", {
  df <- data.frame(
    uuid = vapply(letters[1:5], function(c) strrep(c, 32), character(1)),
    name = c("Flip","Upgrade","Hold","Sell","Invalid"),
    rarity = "Gold", ovr = c(82L, 84L, 82L, 82L, 82L), team = "X",
    ask = 100, bid = 80, raw_ask = 100, raw_bid = 80,
    after_tax_sale = 90,
    flip_profit = c(10, 0, 0, -10, NA),
    flip_roi = c(0.125, 0, 0, -0.10, NA),
    spread_pct = c(0.20, 0.20, 0.20, 0.20, NA),
    liquidity_score = c(1, 1, 1, 1, NA),
    liquidity_n = 10L, liquidity_recent = 10L,
    flip_executable = c(TRUE, TRUE, TRUE, TRUE, FALSE),
    flip_action = c("BUY","HOLD","HOLD","SELL","NO TRADE"),
    flip_reason_codes = "",
    flip_failed_gates = "",
    forecast_ev_7d = c(-0.20, 0, -0.02, 0, NA),
    forecast_direction = c("FORECAST BEARISH","FORECAST FLAT",
                           "FORECAST BEARISH","FORECAST FLAT",
                           "FORECAST UNAVAILABLE"),
    forecast_p_up_7d = NA_real_, forecast_score = 0L,
    forecast_action = "HOLD",
    ev_7d = c(-0.20, 0, -0.02, 0, NA),
    p_up_7d = NA_real_, score = 0L, action = "HOLD", direction = "—",
    new_rank = NA_real_, next_threshold = 85,
    distance_to_threshold = c(3, 1, 3, 3, NA),
    p_upgrade = c(0.2, 0.8, 0.2, 0.1, NA),
    p_downgrade = c(0.1, 0.1, 0.2, 0.7, NA),
    p_cross_next_threshold = c(0.1, 0.8, 0.1, 0.05, NA),
    p_cross_85 = c(0.1, 0.8, 0.1, 0.05, NA),
    p_cross_90 = NA_real_, upgrade_confidence = c(50, 80, 40, 70, 0),
    upgrade_score = c(20, 90, 10, 5, 0),
    upgrade_action = c("HOLD","BUY SPECULATIVE","HOLD","SELL","AVOID"),
    upgrade_reason_codes = "",
    scan_status = c("VALID","VALID","VALID","VALID","INVALID"),
    verdict_status = "OBSERVATIONAL ONLY", tier = "SILVER",
    gates_failed_csv = "", n_trades = 0L,
    ic_point = NA_real_, ic_ci_lo = NA_real_, ic_ci_hi = NA_real_,
    stringsAsFactors = FALSE
  )
  p <- scan_partition(df)
  expect_equal(p$flip_buy$name, "Flip")
  expect_equal(p$upgrade_buy$name, "Upgrade")
  expect_equal(p$holds$name, "Hold")
  expect_equal(p$sell$name, "Sell")
  expect_equal(p$dropped$name, "Invalid")
})

test_that("scan_universe handles empty input gracefully", {
  out <- scan_universe(character(0))
  expect_s3_class(out, "data.frame")
  expect_equal(nrow(out), 0L)
})

test_that("scan_universe drops invalid UUIDs silently before fetching", {
  out <- scan_universe(c("not-a-uuid", "also-bad"))
  expect_equal(nrow(out), 0L)
})

test_that("scan_universe end-to-end with stubbed get_listing returns INVESTABLE row", {
  good_uuid <- strrep("a", 32)
  fake_listing <- make_listing_full(good_uuid, n_orders = 60L)
  # Phase H: enough trades so calibration_held_out_check runs (n >= 30).
  set.seed(1)
  fake_trades <- data.frame(
    p_up = runif(60),
    realized_up = rbinom(60, 1, 0.5),
    brier_t = runif(60, 0.10, 0.30)
  )
  fake_wfcv <- list(n_trades = 60L, ic_point = 0.10,
                    ic_ci = c(0.02, 0.18),
                    brier_point = 0.22, brier_ci = c(0.18, 0.27),
                    hit_rate = 0.55, ci_method = "block", boot_b = 300L,
                    trades = fake_trades)
  fake_cal <- list(ok = TRUE,
                   reason = "Brier 0.260 -> 0.255 (improvement 0.005) on 30 trades",
                   brier_pre = 0.260, brier_post = 0.255, delta = -0.005,
                   n_train = 30L, n_test = 30L)
  orig_get_listing <- get0("get_listing", envir = globalenv())
  orig_wfcv <- get0("walk_forward_cv", envir = globalenv())
  orig_cal  <- get0("calibration_held_out_check", envir = globalenv())
  on.exit({
    if (!is.null(orig_get_listing))
      assign("get_listing", orig_get_listing, envir = globalenv())
    if (!is.null(orig_wfcv))
      assign("walk_forward_cv", orig_wfcv, envir = globalenv())
    if (!is.null(orig_cal))
      assign("calibration_held_out_check", orig_cal, envir = globalenv())
  }, add = TRUE)
  assign("get_listing", function(u) fake_listing, envir = globalenv())
  assign("walk_forward_cv", function(...) fake_wfcv, envir = globalenv())
  assign("calibration_held_out_check", function(...) fake_cal,
         envir = globalenv())

  out <- scan_universe(c(good_uuid), horizon = 7L, rate_delay = 0)
  expect_equal(nrow(out), 1L)
  expect_equal(out$verdict_status[1], "INVESTABLE")
  expect_equal(out$uuid[1], good_uuid)
  expect_equal(out$tier[1], "GOLD")  # Phase H: tier column ships
})

make_listing_full <- function(uuid, name = "X", rarity = "Diamond",
                              ovr = 90L, ask = 100, bid = 90,
                              n_orders = 60L, n_history = 100L) {
  list(
    listing_name = name,
    best_sell_price = ask, best_buy_price = bid,
    item = list(uuid = uuid, name = name, rarity = rarity, ovr = ovr,
                team = "X"),
    completed_orders = lapply(seq_len(n_orders), function(i)
      list(date = sprintf("05/02/2026 %02d:%02d:00",
                          (i %% 24L), (i * 13L) %% 60L),
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
  fake_wfcv <- list(n_trades = 40L, ic_point = 0.10,
                    ic_ci = c(0.02, 0.18),
                    brier_point = 0.22, brier_ci = c(0.18, 0.27),
                    hit_rate = 0.55, ci_method = "block", boot_b = 300L,
                    trades = data.frame(p_up = 0.5, realized_up = 1L,
                                        brier_t = 0.25))
  orig_get_listing <- get0("get_listing", envir = globalenv())
  orig_wfcv <- get0("walk_forward_cv", envir = globalenv())
  on.exit({
    if (!is.null(orig_get_listing))
      assign("get_listing", orig_get_listing, envir = globalenv())
    if (!is.null(orig_wfcv))
      assign("walk_forward_cv", orig_wfcv, envir = globalenv())
  }, add = TRUE)
  assign("get_listing", function(u) fake_listing, envir = globalenv())
  assign("walk_forward_cv", function(...) fake_wfcv, envir = globalenv())

  out <- scan_universe(c(good_uuid), horizon = 7L, rate_delay = 0)
  expect_equal(nrow(out), 1L)
  expect_equal(out$verdict_status[1], "INVESTABLE")
  expect_equal(out$uuid[1], good_uuid)
})

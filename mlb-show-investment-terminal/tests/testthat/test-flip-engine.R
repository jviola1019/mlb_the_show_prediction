test_that("flip_economics applies the 10 percent sell-side tax once", {
  out <- flip_economics(
    sell_price = 1538, buy_price = 1120,
    liquidity = list(score = 1, n = 200L, recent = 120L)
  )
  expect_equal(out$after_tax_sale, 1538 * 0.90)
  expect_equal(out$profit, 1538 * 0.90 - 1120)
  expect_equal(out$roi, (1538 * 0.90 - 1120) / 1120)
  expect_equal(out$action, "BUY")
})

test_that("positive executable flip edge is separate from bearish forecast EV", {
  flip <- flip_economics(
    sell_price = 1538, buy_price = 1120,
    liquidity = list(score = 1, n = 200L, recent = 120L)
  )
  forecast_ev_7d <- -0.329
  expect_gt(flip$profit, 0)
  expect_equal(flip$action, "BUY")
  expect_lt(forecast_ev_7d, 0)
})

test_that("missing bid or ask prevents executable recommendation", {
  no_bid <- flip_economics(
    sell_price = 1000, buy_price = 0,
    liquidity = list(score = 1, n = 20L, recent = 20L)
  )
  expect_false(no_bid$executable)
  expect_equal(no_bid$action, "NO TRADE")
  expect_true("MISSING_BUY_PRICE" %in% no_bid$reason_codes)

  no_ask <- flip_economics(
    sell_price = NA_real_, buy_price = 900,
    liquidity = list(score = 1, n = 20L, recent = 20L)
  )
  expect_false(no_ask$executable)
  expect_equal(no_ask$action, "NO TRADE")
  expect_true("MISSING_SELL_PRICE" %in% no_ask$reason_codes)
})

test_that("no BUY if liquidity or spread is unavailable", {
  no_liq <- flip_economics(sell_price = 1000, buy_price = 800)
  expect_false(no_liq$executable)
  expect_equal(no_liq$action, "NO TRADE")
  expect_true("LIQUIDITY_UNAVAILABLE" %in% no_liq$reason_codes)

  no_spread <- flip_economics(
    sell_price = 1000, buy_price = NA_real_,
    liquidity = list(score = 1, n = 20L, recent = 20L)
  )
  expect_false(no_spread$executable)
  expect_equal(no_spread$action, "NO TRADE")
  expect_true("SPREAD_UNAVAILABLE" %in% no_spread$reason_codes)
})

test_that("manual validation mode agrees with engine formula", {
  engine <- flip_economics(
    sell_price = 1544, buy_price = 1119,
    liquidity = list(score = 1, n = 200L, recent = 100L)
  )
  chk <- validate_flip_formula(1544, 1119, engine = engine, tolerance = 1e-9)
  expect_false(chk$mismatch)
  expect_equal(chk$manual_after_tax_sale, 1544 * 0.90)
  expect_equal(chk$manual_profit, 1544 * 0.90 - 1119)
})

test_that("Python backend bridge returns flip and upgrade contracts", {
  testthat::skip_if_not(python_backend_available(),
                        "Python backend unavailable")
  py <- python_score_card(list(
    raw_ask = 1538,
    raw_bid = 1120,
    liquidity_score = 1,
    liquidity_n = 8,
    liquidity_recent = 3,
    current_ovr = 84,
    rarity = "Gold",
    recent = list(ops = 0.950, avg = 0.320, plateAppearances = 42),
    season = list(ops = 0.780, avg = 0.270, plateAppearances = 180),
    role = "hitter"
  ))
  flip <- python_result_to_flip(py)
  upgrade <- python_result_to_upgrade(py)
  val <- python_result_to_validation(py)

  expect_equal(flip$after_tax_sale, 1538 * 0.90)
  expect_equal(flip$profit, 1538 * 0.90 - 1120)
  expect_equal(flip$action, "BUY")
  expect_true("PYTHON_BACKEND" %in% upgrade$reason_codes)
  expect_equal(upgrade$distance_to_85, 1)
  expect_false(val$mismatch)
})

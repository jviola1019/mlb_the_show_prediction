test_that("z_to_delta_ovr binning matches v3.3 exactly", {
  expect_equal(z_to_delta_ovr( 2.5),  3L)
  expect_equal(z_to_delta_ovr( 1.5),  2L)
  expect_equal(z_to_delta_ovr( 0.8),  1L)
  expect_equal(z_to_delta_ovr( 0.3),  0L)
  expect_equal(z_to_delta_ovr(-0.3),  0L)
  expect_equal(z_to_delta_ovr(-0.8), -1L)
  expect_equal(z_to_delta_ovr(-1.5), -2L)
  expect_equal(z_to_delta_ovr(-2.5), -3L)
  expect_equal(z_to_delta_ovr(NA_real_), 0L)
})

test_that("rarity_pct_per_ovr returns correct multipliers", {
  expect_equal(rarity_pct_per_ovr("Diamond"), 0.15)
  expect_equal(rarity_pct_per_ovr("gold"),    0.20)
  expect_equal(rarity_pct_per_ovr("silver"),  0.10)
  expect_equal(rarity_pct_per_ovr("bronze"),  0.05)
  expect_equal(rarity_pct_per_ovr("common"),  0)
  expect_equal(rarity_pct_per_ovr(NA),        0)
})

test_that("Gold->Diamond boundary at OVR 85 = high risk + 150% jump", {
  bj <- boundary_jump(current_ovr = 84, delta_ovr = 3L, rarity = "gold")
  expect_true(bj$crosses)
  expect_equal(bj$jump_pct, 1.50)
  expect_equal(bj$risk, "high")

  # No crossing if delta keeps under 85
  bj2 <- boundary_jump(82, 2L, "gold")
  expect_false(bj2$crosses)
  expect_equal(bj2$jump_pct, 0)
  expect_equal(bj2$risk, "low")
})

test_that("Silver->Gold boundary at OVR 80 = high risk + 80% jump", {
  bj <- boundary_jump(79, 2L, "silver")
  expect_true(bj$crosses)
  expect_equal(bj$jump_pct, 0.80)
  expect_equal(bj$risk, "high")
})

test_that("Bronze->Silver boundary at OVR 75 = medium risk + 50% jump", {
  bj <- boundary_jump(73, 3L, "bronze")
  expect_true(bj$crosses)
  expect_equal(bj$jump_pct, 0.50)
  expect_equal(bj$risk, "medium")
})

test_that("Negative delta never crosses boundary upward", {
  bj <- boundary_jump(86, -2L, "gold")
  expect_false(bj$crosses)
  expect_equal(bj$jump_pct, 0)
})

test_that("ovr_z_score hitter averages OPS + BA components", {
  # OPS recent +0.110 (= 1 std), BA recent +0.045 (= 1 std) => z = 1.0
  recent <- list(ops = 0.910, avg = 0.345)
  season <- list(ops = 0.800, avg = 0.300)
  r <- ovr_z_score(recent, season, role = "hitter")
  expect_equal(unname(r$z), 1.0, tolerance = 1e-9)
  expect_equal(names(r$components), c("ops", "ba"))
})

test_that("ovr_z_score pitcher sign-flips ERA + WHIP", {
  # ERA recent < season => z positive (improvement)
  recent <- list(era = 2.40, whip = 1.00)
  season <- list(era = 3.60, whip = 1.20)
  r <- ovr_z_score(recent, season, role = "pitcher")
  expect_gt(unname(r$z), 0)
})

test_that("predict_price_change end-to-end at gold->diamond boundary", {
  # ops diff 0.300 -> z_ops = 2.727; ba diff 0.100 -> z_ba = 2.222; mean 2.475
  recent <- list(ops = 1.100, avg = 0.400)
  season <- list(ops = 0.800, avg = 0.300)
  out <- predict_price_change(recent, season, role = "hitter",
                              current_ovr = 84, rarity = "gold")
  expect_equal(out$delta_ovr, 3L)  # |z| > 2
  expect_true(out$boundary$crosses)
  expect_equal(out$total_pct, 1.50)
  expect_equal(out$confidence, "high")
})

test_that("Confidence labels: high/medium/low by |z|", {
  expect_equal(ovr_confidence( 2.0), "high")
  expect_equal(ovr_confidence( 1.0), "medium")
  expect_equal(ovr_confidence( 0.3), "low")
  expect_equal(ovr_confidence(-1.6), "high")
  expect_equal(ovr_confidence(NA),   "low")
})

test_that("distance to threshold is rarity aware", {
  expect_equal(distance_to_ovr_threshold(64, "Common"), 1)
  expect_equal(distance_to_ovr_threshold(74, "Bronze"), 1)
  expect_equal(distance_to_ovr_threshold(79, "Silver"), 1)
  expect_equal(distance_to_ovr_threshold(84, "Gold"), 1)
  expect_equal(distance_to_ovr_threshold(89, "Diamond"), 1)
  expect_equal(distance_to_ovr(80, 85), 5)
  expect_equal(distance_to_ovr(75, 85), 10)
  expect_equal(next_ovr_threshold(95, "Diamond"), NA_real_)
})

test_that("near-threshold gold candidate outranks farther gold candidate", {
  recent <- list(ops = 1.050, avg = 0.370, plateAppearances = 50)
  season <- list(ops = 0.800, avg = 0.290, plateAppearances = 180)
  near <- roster_upgrade_engine(recent, season, "hitter", 84, "Gold")
  far <- roster_upgrade_engine(recent, season, "hitter", 82, "Gold")
  expect_gt(near$p_cross_next_threshold, far$p_cross_next_threshold)
  expect_gt(near$upgrade_score, far$upgrade_score)
})

test_that("silver and bronze use 80 and 75 thresholds", {
  recent <- list(ops = 1.000, avg = 0.350, plateAppearances = 45)
  season <- list(ops = 0.820, avg = 0.290, plateAppearances = 160)
  silver <- roster_upgrade_engine(recent, season, "hitter", 79, "Silver")
  bronze <- roster_upgrade_engine(recent, season, "hitter", 74, "Bronze")
  expect_equal(silver$next_threshold, 80)
  expect_equal(silver$distance_to_threshold, 1)
  expect_equal(silver$distance_to_85, 6)
  expect_equal(bronze$next_threshold, 75)
  expect_equal(bronze$distance_to_threshold, 1)
  expect_equal(bronze$distance_to_85, 11)
})

test_that("new_rank crossing threshold becomes reason code and raises confidence", {
  recent <- list(ops = 0.840, avg = 0.290, plateAppearances = 35)
  season <- list(ops = 0.800, avg = 0.280, plateAppearances = 120)
  base <- roster_upgrade_engine(recent, season, "hitter", 84, "Gold")
  crossed <- roster_upgrade_engine(recent, season, "hitter", 84, "Gold",
                                   new_rank = 85)
  expect_true("NEW_RANK_CROSSES_THRESHOLD" %in% crossed$reason_codes)
  expect_gte(crossed$p_cross_next_threshold, 0.85)
  expect_gt(crossed$confidence, base$confidence)
  expect_equal(crossed$action, "BUY SPECULATIVE")
})

test_that("missing stats and missing new_rank is unavailable rather than guessed", {
  out <- roster_upgrade_engine(list(), list(), "hitter", 82, "Gold")
  expect_equal(out$action, "AVOID")
  expect_equal(out$confidence, 0)
  expect_true(is.na(out$p_upgrade))
  expect_true("RECENT_STATS_UNAVAILABLE" %in% out$reason_codes)
})

load_fixture <- function() {
  p <- testthat::test_path("..", "..", "data", "roster_updates.rds")
  readRDS(p)
}

test_that("roster_banner highlights upcoming attribute update with amber", {
  updates <- load_fixture()
  # 2026-05-13 -> next is 2026-05-15 attribute
  out <- roster_banner(today = as.Date("2026-05-13"), updates = updates)
  html <- as.character(htmltools::renderTags(out)$html)
  expect_true(grepl("roster-attribute", html))
  expect_true(grepl("IN 2D", html) || grepl("ATTR", html))
})

test_that("roster_banner countdown shows IN 13D for 2026-05-02 (next attr 5/15)", {
  updates <- load_fixture()
  out <- roster_banner(today = as.Date("2026-05-02"), updates = updates)
  html <- as.character(htmltools::renderTags(out)$html)
  # Next is 2026-05-08 (transaction). 6 days.
  expect_true(grepl("IN 6D", html))
  expect_true(grepl("roster-transaction", html))
})

test_that("roster_banner returns 'TODAY' on the exact date", {
  updates <- load_fixture()
  out <- roster_banner(today = as.Date("2026-05-15"), updates = updates)
  html <- as.character(htmltools::renderTags(out)$html)
  expect_true(grepl("TODAY", html))
})

test_that("roster_banner returns empty class when schedule exhausted", {
  updates <- load_fixture()
  out <- roster_banner(today = as.Date("2027-01-01"), updates = updates)
  html <- as.character(htmltools::renderTags(out)$html)
  expect_true(grepl("roster-empty", html))
})

test_that("Imminent (<=2d) non-attribute shows SOON pill", {
  updates <- load_fixture()
  # 2026-04-01 -> next is 2026-04-03 transaction (2 days)
  out <- roster_banner(today = as.Date("2026-04-01"), updates = updates)
  html <- as.character(htmltools::renderTags(out)$html)
  expect_true(grepl("SOON", html))
})

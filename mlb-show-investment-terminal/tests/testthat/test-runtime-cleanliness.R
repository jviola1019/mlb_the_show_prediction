# Phase H: runtime-cleanliness guards.
# These tests run from `tests/testthat/` so we walk up to repo root.

.repo_root <- function() {
  here <- normalizePath(getwd(), winslash = "/")
  # If we're in tests/testthat or test-scratch dir, climb two levels.
  if (basename(here) == "testthat") return(dirname(dirname(here)))
  if (basename(here) == "tests")    return(dirname(here))
  here
}

test_that("no synthetic data files have leaked back into data/", {
  root <- .repo_root()
  data_dir <- file.path(root, "data")
  if (!dir.exists(data_dir)) skip("data/ not present in this checkout")
  hits <- list.files(data_dir, pattern = "synthetic_", full.names = TRUE)
  expect_equal(hits, character(0))
})

test_that("favicon.ico and favicon.svg are shipped under www/", {
  root <- .repo_root()
  expect_true(file.exists(file.path(root, "www", "favicon.ico")))
  expect_true(file.exists(file.path(root, "www", "favicon.svg")))
})

test_that("R/quant_scan.R does not reference synthetic universes at runtime", {
  root <- .repo_root()
  src <- file.path(root, "R", "quant_scan.R")
  if (!file.exists(src)) skip("quant_scan.R not present")
  txt <- readLines(src, warn = FALSE)
  # Allow the word in comments — the rule is no LIVE call to anything
  # named like `synthetic_universe`/`fake_universe` etc.
  bad <- grep("(synthetic|fake)_(universe|cards|listings|prices)",
              txt, value = TRUE, perl = TRUE)
  expect_equal(bad, character(0))
})

test_that("README claims six tabs", {
  root <- .repo_root()
  readme <- file.path(root, "README.md")
  if (!file.exists(readme)) skip("README.md not present")
  txt <- paste(readLines(readme, warn = FALSE), collapse = "\n")
  # Either 'Six tabs' or 'six tabs' should appear after Phase H ships.
  expect_match(txt, "[Ss]ix tabs")
})

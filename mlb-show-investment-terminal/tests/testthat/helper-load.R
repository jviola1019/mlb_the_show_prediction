# helper-load.R — make package functions visible to test_that() blocks.
# Sourced automatically by testthat before each test file.

if (!exists("normalize_name", mode = "function", envir = globalenv())) {
  pkg_root <- tryCatch(
    testthat::test_path("..", ".."),
    error = function(e) {
      # Fallback: walk up until we find DESCRIPTION
      d <- getwd()
      while (!file.exists(file.path(d, "DESCRIPTION")) && d != dirname(d)) {
        d <- dirname(d)
      }
      d
    }
  )
  r_files <- list.files(file.path(pkg_root, "R"), pattern = "\\.R$", full.names = TRUE)
  for (f in r_files) source(f, local = globalenv())
}

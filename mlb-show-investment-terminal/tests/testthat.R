library(testthat)

# Source R/ files directly so tests run without installing the package.
# This is intentional — the app uses the same `source(R/*.R)` pattern at runtime
# (see app.R) for shinyapps.io portability.
pkg_root <- normalizePath(file.path(dirname(sys.frame(1)$ofile), ".."), winslash = "/")
r_files <- list.files(file.path(pkg_root, "R"), pattern = "\\.R$", full.names = TRUE)
for (f in r_files) source(f, local = globalenv())

test_dir(file.path(pkg_root, "tests/testthat"), reporter = "summary")

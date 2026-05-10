#' Thin bridge to the Python model/data backend.
#'
#' Shiny remains the UI shell. Flip math, upgrade-threshold scoring, validation
#' math, and historical backtest metrics can be executed by the Python package
#' under python/mlb_show_terminal. All calls are deterministic temp-file
#' exchanges; no persistent local state is created.

.python_backend_root <- function() {
  d <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
  while (!file.exists(file.path(d, "DESCRIPTION")) && d != dirname(d)) {
    d <- dirname(d)
  }
  candidates <- c(
    file.path(getwd(), "python"),
    file.path(d, "python"),
    file.path(dirname(getwd()), "mlb-show-investment-terminal", "python")
  )
  candidates <- candidates[dir.exists(candidates)]
  if (length(candidates) == 0L) return(NA_character_)
  normalizePath(candidates[[1L]], winslash = "/", mustWork = TRUE)
}

.python_exe <- function() {
  configured <- Sys.getenv("MLB_SHOW_PYTHON", unset = "")
  if (nzchar(configured)) return(configured)
  found <- Sys.which("python")
  if (nzchar(found)) return(unname(found))
  found <- Sys.which("python3")
  if (nzchar(found)) return(unname(found))
  ""
}

.with_pythonpath <- function(root, expr) {
  old <- Sys.getenv("PYTHONPATH", unset = NA_character_)
  Sys.setenv(PYTHONPATH = root)
  on.exit({
    if (is.na(old)) Sys.unsetenv("PYTHONPATH") else Sys.setenv(PYTHONPATH = old)
  }, add = TRUE)
  force(expr)
}

.shell_args <- function(args) {
  vapply(args, function(x) {
    x <- as.character(x)
    if (grepl("[[:space:];\"&()]", x, perl = TRUE)) shQuote(x) else x
  }, character(1), USE.NAMES = FALSE)
}

#' Return TRUE when the Python backend can be imported.
#' @export
python_backend_available <- function() {
  cached <- getOption("mlb_show_python_backend_available", NULL)
  if (!is.null(cached)) return(isTRUE(cached))
  root <- .python_backend_root()
  py <- .python_exe()
  ok <- is.finite(nchar(root)) && !is.na(root) && nzchar(py)
  if (ok) {
    probe <- tryCatch(
      .with_pythonpath(root, system2(py, .shell_args(c("-c", "import mlb_show_terminal")),
                                    stdout = TRUE, stderr = TRUE)),
      error = function(e) structure(character(0), status = 1L)
    )
    ok <- is.null(attr(probe, "status")) || identical(attr(probe, "status"), 0L)
  }
  options(mlb_show_python_backend_available = ok)
  ok
}

.python_json_call <- function(args, payload = NULL) {
  if (!python_backend_available()) return(NULL)
  root <- .python_backend_root()
  py <- .python_exe()
  out <- tempfile(fileext = ".json")
  in_file <- NULL
  on.exit({
    if (!is.null(in_file) && file.exists(in_file)) unlink(in_file)
    if (file.exists(out)) unlink(out)
  }, add = TRUE)
  if (!is.null(payload)) {
    in_file <- tempfile(fileext = ".json")
    jsonlite::write_json(payload, in_file, auto_unbox = TRUE,
                         null = "null", na = "null")
    args <- c(args, "--input", normalizePath(in_file, winslash = "/", mustWork = TRUE))
  }
  args <- c("-m", "mlb_show_terminal.cli", args,
            "--output", normalizePath(out, winslash = "/", mustWork = FALSE))
  res <- tryCatch(
    .with_pythonpath(root, system2(py, .shell_args(args),
                                  stdout = TRUE, stderr = TRUE)),
    error = function(e) structure(conditionMessage(e), status = 1L)
  )
  status <- attr(res, "status")
  if (!is.null(status) && !identical(status, 0L)) return(NULL)
  if (!file.exists(out)) return(NULL)
  tryCatch(jsonlite::read_json(out, simplifyVector = FALSE), error = function(e) NULL)
}

#' Score one card/listing through the Python backend.
#' @export
python_score_card <- function(row) {
  .python_json_call("score-row", payload = row)
}

.py_num <- function(x) {
  if (is.null(x) || length(x) == 0L) return(NA_real_)
  suppressWarnings(as.numeric(x[[1L]]))
}

.py_int <- function(x) {
  out <- .py_num(x)
  if (!is.finite(out)) return(NA_integer_)
  as.integer(out)
}

.py_chr <- function(x, default = NA_character_) {
  if (is.null(x) || length(x) == 0L) return(default)
  as.character(x[[1L]])
}

.py_lgl <- function(x) {
  if (is.null(x) || length(x) == 0L) return(FALSE)
  isTRUE(x[[1L]])
}

.py_csv <- function(x) {
  if (is.null(x) || length(x) == 0L) return("")
  vals <- unique(as.character(unlist(x, use.names = FALSE)))
  vals <- vals[nchar(vals) > 0L]
  paste(vals, collapse = ",")
}

#' Convert a Python flip payload into the R engine contract.
#' @export
python_result_to_flip <- function(py) {
  f <- py$flip
  if (is.null(f)) return(NULL)
  list(
    sell_price = .py_num(f$sell_price),
    buy_price = .py_num(f$buy_price),
    after_tax_sale = .py_num(f$after_tax_sale),
    profit = .py_num(f$profit),
    roi = .py_num(f$roi),
    spread_pct = .py_num(f$spread_pct),
    liquidity_score = .py_num(f$liquidity_score),
    liquidity_n = .py_int(f$liquidity_n),
    liquidity_recent = .py_int(f$liquidity_recent),
    executable = .py_lgl(f$executable),
    action = .py_chr(f$action, "NO TRADE"),
    reason_codes = as.character(unlist(f$reason_codes %||% list(),
                                       use.names = FALSE)),
    reason_codes_csv = .py_chr(f$reason_codes_csv, .py_csv(f$reason_codes)),
    failed_gates = as.character(unlist(f$failed_gates %||% list(),
                                       use.names = FALSE)),
    failed_gates_csv = .py_chr(f$failed_gates_csv, .py_csv(f$failed_gates))
  )
}

#' Convert a Python upgrade payload into the R engine contract.
#' @export
python_result_to_upgrade <- function(py) {
  u <- py$upgrade
  if (is.null(u)) return(NULL)
  list(
    current_ovr = .py_num(u$current_ovr),
    rarity = .py_chr(u$rarity, NA_character_),
    new_rank = .py_num(u$new_rank),
    next_threshold = .py_num(u$next_threshold),
    distance_to_threshold = .py_num(u$distance_to_threshold),
    distance_to_85 = .py_num(u$distance_to_85),
    distance_to_90 = .py_num(u$distance_to_90),
    p_upgrade = .py_num(u$p_upgrade),
    p_downgrade = .py_num(u$p_downgrade),
    p_cross_next_threshold = .py_num(u$p_cross_next_threshold),
    p_cross_85 = .py_num(u$p_cross_85),
    p_cross_90 = .py_num(u$p_cross_90),
    confidence = .py_num(u$confidence),
    confidence_label = .py_chr(u$confidence_label, "low"),
    recent_vs_season_delta = .py_chr(u$recent_vs_season_delta, ""),
    exact_delta_ovr = .py_int(u$exact_delta_ovr),
    z = .py_num(u$z),
    components = u$components %||% list(),
    upgrade_score = .py_num(u$upgrade_score),
    action = .py_chr(u$action, "HOLD"),
    reason_codes = as.character(unlist(u$reason_codes %||% list(),
                                       use.names = FALSE)),
    reason_codes_csv = .py_chr(u$reason_codes_csv, .py_csv(u$reason_codes))
  )
}

#' Convert Python validation payload into the R validation contract.
#' @export
python_result_to_validation <- function(py) {
  v <- py$validation
  if (is.null(v)) return(NULL)
  list(
    manual_after_tax_sale = .py_num(v$manual_after_tax_sale),
    manual_profit = .py_num(v$manual_profit),
    manual_roi = .py_num(v$manual_roi),
    model_after_tax_sale = .py_num(v$model_after_tax_sale),
    model_profit = .py_num(v$model_profit),
    model_roi = .py_num(v$model_roi),
    max_abs_diff = .py_num(v$max_abs_diff),
    tolerance = .py_num(v$tolerance),
    mismatch = .py_lgl(v$mismatch)
  )
}

#' Run Python historical backtest metrics from explicit prediction/label files.
#' @export
python_backtest_files <- function(predictions, labels, n_bins = 5L) {
  if (!python_backend_available()) return(NULL)
  if (!file.exists(predictions) || !file.exists(labels)) return(NULL)
  root <- .python_backend_root()
  py <- .python_exe()
  out <- tempfile(fileext = ".json")
  on.exit(if (file.exists(out)) unlink(out), add = TRUE)
  args <- c(
    "-m", "mlb_show_terminal.cli", "backtest",
    "--predictions", normalizePath(predictions, winslash = "/", mustWork = TRUE),
    "--labels", normalizePath(labels, winslash = "/", mustWork = TRUE),
    "--n-bins", as.character(as.integer(n_bins)),
    "--output", normalizePath(out, winslash = "/", mustWork = FALSE)
  )
  res <- tryCatch(
    .with_pythonpath(root, system2(py, .shell_args(args),
                                  stdout = TRUE, stderr = TRUE)),
    error = function(e) structure(conditionMessage(e), status = 1L)
  )
  status <- attr(res, "status")
  if (!is.null(status) && !identical(status, 0L)) return(NULL)
  if (!file.exists(out)) return(NULL)
  tryCatch(jsonlite::read_json(out, simplifyVector = FALSE), error = function(e) NULL)
}

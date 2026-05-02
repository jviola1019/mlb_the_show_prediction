#' Utility functions for the MLB Show Investment Terminal
#'
#' Pure functions: name normalization, formatting, validation.
#' No side effects; everything testable.

#' Normalize a player name to a canonical search form.
#'
#' Accepts any caps and a few common formats. Critically:
#' - Preserves trailing periods (Jr., Sr., III.) since The Show DB stores them
#' - Reverses "Last, First" to "First Last"
#' - Keeps accents (Acuña), apostrophes (O'Brien), hyphens (Hyun-Jin Ryu)
#' - Strips control chars and collapses whitespace
#'
#' @param raw character. Raw user input.
#' @return character. Cleaned string suitable for the `name=` API parameter.
#' @export
normalize_name <- function(raw) {
  if (!is.character(raw) || length(raw) != 1 || is.na(raw)) return("")
  s <- trimws(raw)
  if (nchar(s) == 0) return("")

  # "Last, First" -> "First Last"
  if (grepl("^[^,]+,\\s*[^,]+$", s)) {
    parts <- trimws(strsplit(s, ",", fixed = TRUE)[[1]])
    if (length(parts) == 2L && all(nchar(parts) > 0)) {
      s <- paste(parts[2], parts[1])
    }
  }

  # Strip control chars + collapse whitespace (POSIX class avoids literal NUL in source)
  s <- gsub("[[:cntrl:]]", "", s, perl = TRUE)
  s <- gsub("\\s+", " ", s, perl = TRUE)
  # Strip leading punctuation/whitespace (incl. leading dots).
  # Trailing periods preserved (Jr., Sr., III.) — only strip trailing comma/dash/whitespace.
  s <- gsub("^[.,\\-\\s]+", "", s, perl = TRUE)
  s <- gsub("[,\\-\\s]+$", "", s, perl = TRUE)
  trimws(s)
}

#' Format a fraction as a percentage.
#' @param x numeric.
#' @param d integer. Decimal digits.
#' @return character. e.g. "12.3%" or "—" if NA.
#' @export
fmt_pct <- function(x, d = 1L) {
  if (length(x) == 0L || is.na(x) || !is.finite(x)) return("\u2014")
  sprintf(paste0("%.", d, "f%%"), x * 100)
}

#' Signed percent: prepends + for non-negative.
#' @export
fmt_signed <- function(x, d = 1L) {
  if (length(x) == 0L || is.na(x) || !is.finite(x)) return("\u2014")
  prefix <- if (x >= 0) "+" else ""
  paste0(prefix, sprintf(paste0("%.", d, "f%%"), x * 100))
}

#' Format a stub count: 12345 -> "12,345s"
#' @export
fmt_stubs <- function(x) {
  if (length(x) == 0L || is.na(x) || !is.finite(x)) return("\u2014")
  paste0(formatC(round(x), big.mark = ",", format = "d"), "s")
}

#' Validate a 32-char hex UUID (case-insensitive).
#' @export
is_valid_uuid <- function(uuid) {
  if (!is.character(uuid) || length(uuid) != 1 || is.na(uuid)) return(FALSE)
  grepl("^[a-fA-F0-9]{32}$", trimws(uuid))
}

#' Map a rarity string to a Bootstrap badge tone.
#' @export
rarity_to_tone <- function(rarity) {
  if (is.null(rarity) || is.na(rarity) || rarity == "") return("secondary")
  r <- tolower(rarity)
  if (grepl("diamond", r)) return("primary")
  if (grepl("gold", r))    return("warning")
  if (grepl("silver", r))  return("secondary")
  if (grepl("bronze", r))  return("danger")
  "secondary"
}

#' Convert American odds-style positive/negative -> implied probability.
#' Used in display only; not in core math.
#' @export
implied_prob_from_american <- function(odds) {
  if (is.na(odds) || !is.finite(odds)) return(NA_real_)
  if (odds >= 100) return(100 / (odds + 100))
  if (odds <= -100) return(-odds / (-odds + 100))
  NA_real_
}

#' Compute log returns from a price vector (drops NA, zero, negative).
#' @export
log_returns <- function(prices) {
  prices <- as.numeric(prices)
  prices <- prices[!is.na(prices) & is.finite(prices) & prices > 0]
  if (length(prices) < 2L) return(numeric(0))
  diff(log(prices))
}

#' Pearson correlation, returns 0 on invalid input rather than NA (UI-safe).
#' @export
safe_cor <- function(x, y) {
  if (length(x) != length(y) || length(x) < 2L) return(0)
  if (sd(x, na.rm = TRUE) == 0 || sd(y, na.rm = TRUE) == 0) return(0)
  out <- suppressWarnings(stats::cor(x, y, use = "pairwise.complete.obs"))
  if (is.na(out)) 0 else out
}

#' Liquidity score: log10-scaled count of completed orders in last 24h.
#' @param orders list. Each element should have a `date` field.
#' @return list with score [0,1], n, recent.
#' @export
liquidity_score <- function(orders) {
  if (!is.list(orders) || length(orders) == 0L) {
    return(list(score = 0, n = 0L, recent = 0L))
  }
  now <- Sys.time()
  day_ago <- now - 24 * 3600
  dates <- vapply(orders, function(o) {
    d <- o$date %||% o$timestamp
    if (is.null(d)) return(NA_real_)
    as.numeric(suppressWarnings(as.POSIXct(d)))
  }, numeric(1))
  recent <- sum(!is.na(dates) & dates >= as.numeric(day_ago))
  list(
    score = min(1, log10(max(1, recent)) / log10(150)),
    n = length(orders),
    recent = recent
  )
}

# Null-coalescing operator
`%||%` <- function(a, b) if (is.null(a)) b else a

#' The Show API client (server-side, no CORS).
#'
#' All calls bypass browser CORS by running in R. The client supports the
#' year fallback 26 -> 25 -> 24 (today is 2026-05-02; The Show 26 launched
#' 2026-03-17 but legacy hosts still serve older databases).
#'
#' Memoised with a 10-minute in-memory TTL so the UI feels instant on
#' repeat lookups during a session.

.theshow_cache <- NULL

.theshow_init_cache <- function() {
  if (is.null(.theshow_cache)) {
    .theshow_cache <<- cachem::cache_mem(
      max_size = 32 * 1024^2,
      max_age = 600
    )
  }
  invisible(NULL)
}

#' Internal: GET request with year fallback.
#' @keywords internal
theshow_request <- function(path, query = list(),
                            years = c(26L, 25L, 24L), timeout = 15) {
  last_err <- NULL
  for (yr in years) {
    host <- sprintf("https://mlb%d.theshow.com", yr)
    req <- httr2::request(host) |>
      httr2::req_url_path_append(path) |>
      httr2::req_url_query(!!!query) |>
      httr2::req_user_agent("mlbshowterminal/1.0 (server-side R Shiny)") |>
      httr2::req_timeout(timeout) |>
      httr2::req_retry(max_tries = 3,
                       backoff = function(i) 2^i,
                       is_transient = function(resp) {
                         httr2::resp_status(resp) %in% c(408, 429, 500, 502,
                                                          503, 504)
                       })
    resp <- tryCatch(
      httr2::req_perform(req),
      httr2_http_404 = function(e) NULL,
      httr2_http_4xx = function(e) NULL,
      error = function(e) {
        last_err <<- conditionMessage(e); NULL
      }
    )
    if (is.null(resp)) next
    if (httr2::resp_status(resp) >= 400) next
    body <- tryCatch(
      httr2::resp_body_json(resp, simplifyVector = FALSE),
      error = function(e) NULL
    )
    if (is.null(body)) next
    # Empty listings? try next year
    if (!is.null(body$listings) && length(body$listings) == 0L) next
    body$.year_used <- yr
    body$.host <- host
    return(body)
  }
  list(error = last_err %||% "no usable response", listings = list(),
       .year_used = NA_integer_)
}

#' Search The Show listings by name.
#'
#' @param name character. Player name (will be normalized).
#' @param page integer.
#' @return list with `listings` (list of items), `year` (used year),
#'   `source_url` (clickable URL for verification).
#' @export
search_card_uncached <- function(name, page = 1L) {
  q <- normalize_name(name)
  if (nchar(q) == 0L) {
    return(list(listings = list(), year = NA_integer_,
                source_url = NA_character_,
                error = "empty query"))
  }
  body <- theshow_request(
    "apis/listings.json",
    query = list(type = "mlb_card", name = q, page = page)
  )
  list(
    listings = body$listings %||% list(),
    year = body$.year_used,
    source_url = if (!is.na(body$.year_used)) {
      sprintf("%s/apis/listings.json?type=mlb_card&name=%s&page=%d",
              body$.host, utils::URLencode(q, reserved = TRUE), page)
    } else NA_character_,
    error = body$error
  )
}

#' Memoised public entry point.
#' @export
search_card <- function(name, page = 1L) {
  .theshow_init_cache()
  if (!is.function(.search_card_memoised)) {
    .search_card_memoised <<- memoise::memoise(
      search_card_uncached, cache = .theshow_cache
    )
  }
  .search_card_memoised(name, page)
}
.search_card_memoised <- NULL

#' Fetch a single listing by UUID.
#' @export
get_listing_uncached <- function(uuid) {
  if (!is_valid_uuid(uuid)) {
    return(list(error = "invalid uuid", item = NULL))
  }
  body <- theshow_request(
    "apis/listing.json",
    query = list(uuid = uuid)
  )
  if (!is.null(body$error) && length(body) <= 3L) {
    return(list(error = body$error, item = NULL))
  }
  body$source_url <- if (!is.na(body$.year_used)) {
    sprintf("%s/apis/listing.json?uuid=%s", body$.host, uuid)
  } else NA_character_
  body
}

#' Memoised public entry point.
#' @export
get_listing <- function(uuid) {
  .theshow_init_cache()
  if (!is.function(.get_listing_memoised)) {
    .get_listing_memoised <<- memoise::memoise(
      get_listing_uncached, cache = .theshow_cache
    )
  }
  .get_listing_memoised(uuid)
}
.get_listing_memoised <- NULL

#' Extract a tidy price-history data frame from a listing payload.
#' @export
parse_price_str <- function(p) {
  if (is.null(p) || (is.atomic(p) && length(p) == 1L && is.na(p))) {
    return(NA_real_)
  }
  if (is.numeric(p)) return(as.numeric(p))
  s <- gsub(",", "", as.character(p), fixed = TRUE)
  v <- suppressWarnings(as.numeric(s))
  if (length(v) == 0L) NA_real_ else v
}

parse_one_ts <- function(d, default_year = format(Sys.Date(), "%Y")) {
  if (is.null(d) || (is.atomic(d) && length(d) == 1L && is.na(d))) {
    return(NA_real_)
  }
  d <- as.character(d)
  # Bare MM/DD -> append current year so as.POSIXct can parse.
  if (grepl("^\\d{1,2}/\\d{1,2}$", d)) d <- paste0(d, "/", default_year)
  for (fmt in c("%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y")) {
    v <- suppressWarnings(as.POSIXct(d, format = fmt, tz = "UTC"))
    if (!is.na(v)) return(as.numeric(v))
  }
  NA_real_
}

#' Build a tidy timestamped price series from a listing payload.
#'
#' Prefers `completed_orders` (200 tick-level samples with full timestamps)
#' over `price_history` (~daily candles, MM/DD-only dates).
#' @export
extract_price_history <- function(listing) {
  empty <- data.frame(timestamp = as.POSIXct(character(0), tz = "UTC"),
                      price = numeric(0))
  co <- listing$completed_orders %||% list()
  if (length(co) >= 8L) {
    ts <- vapply(co, function(r) parse_one_ts(r$date %||% r$timestamp),
                 numeric(1))
    px <- vapply(co, function(r) parse_price_str(r$price), numeric(1))
    ok <- is.finite(ts) & is.finite(px) & px > 0
    if (sum(ok) >= 8L) {
      df <- data.frame(
        timestamp = as.POSIXct(ts[ok], origin = "1970-01-01", tz = "UTC"),
        price = px[ok]
      )
      df <- df[order(df$timestamp), , drop = FALSE]
      rownames(df) <- NULL
      return(df)
    }
  }
  ph <- listing$price_history %||% listing$item$price_history %||% list()
  if (length(ph) == 0L) return(empty)
  ts <- vapply(ph, function(r) parse_one_ts(r$date %||% r$timestamp),
               numeric(1))
  # price_history rows have best_buy/best_sell candles; midpoint is most useful.
  px <- vapply(ph, function(r) {
    bs <- parse_price_str(r$best_sell_price)
    bb <- parse_price_str(r$best_buy_price)
    vals <- c(bs, bb)
    vals <- vals[is.finite(vals) & vals > 0]
    if (length(vals) == 0L) NA_real_ else mean(vals)
  }, numeric(1))
  ok <- is.finite(ts) & is.finite(px) & px > 0
  df <- data.frame(
    timestamp = as.POSIXct(ts[ok], origin = "1970-01-01", tz = "UTC"),
    price = px[ok]
  )
  df <- df[order(df$timestamp), , drop = FALSE]
  rownames(df) <- NULL
  df
}

#' Force-clear memoise caches.
#' @export
theshow_clear_cache <- function() {
  if (!is.null(.theshow_cache)) .theshow_cache$reset()
  invisible(NULL)
}

#' Discover top-of-market UUIDs for a given rarity, live from listings.json.
#'
#' No bundled UUID list — UUIDs change per game year and per attribute update,
#' so the universe is re-discovered on demand. Memoised with 5-min TTL because
#' the universe shifts slowly (top-N composition is stable across short
#' windows).
#'
#' @param rarity character; one of "Diamond"/"Gold"/"Silver"/"Bronze".
#' @param pages integer >= 1; number of `listings.json?page=` pages to pull.
#' @param max_per_page integer; cap on UUIDs returned per page.
#' @return data.frame(uuid, name, rarity, ovr, team, ask, bid).
#' @export
discover_top_listings_uncached <- function(
  rarity = c("Diamond","Gold","Silver","Bronze"),
  pages = 1L, max_per_page = 25L) {
  rarity <- match.arg(rarity)
  rows <- list()
  for (p in seq_len(max(1L, as.integer(pages)))) {
    body <- theshow_request(
      "apis/listings.json",
      query = list(type = "mlb_card", page = p)
    )
    listings <- body$listings %||% list()
    if (length(listings) == 0L) break
    for (L in listings) {
      it <- L$item %||% list()
      r <- it$rarity %||% NA_character_
      if (!is.na(r) && tolower(r) == tolower(rarity)) {
        rows[[length(rows) + 1L]] <- data.frame(
          uuid = it$uuid %||% NA_character_,
          name = it$name %||% L$listing_name %||% NA_character_,
          rarity = r,
          ovr = as.integer(it$ovr %||% NA_integer_),
          team = it$team %||% NA_character_,
          ask = as.numeric(L$best_sell_price %||% NA_real_),
          bid = as.numeric(L$best_buy_price %||% NA_real_),
          stringsAsFactors = FALSE
        )
      }
      if (length(rows) >= max_per_page * p) break
    }
  }
  if (length(rows) == 0L) {
    return(data.frame(uuid = character(0), name = character(0),
                      rarity = character(0), ovr = integer(0),
                      team = character(0), ask = numeric(0),
                      bid = numeric(0)))
  }
  df <- do.call(rbind, rows)
  df <- df[!is.na(df$uuid) & vapply(df$uuid, is_valid_uuid, logical(1)), ,
           drop = FALSE]
  df <- df[order(-df$ask), , drop = FALSE]  # sort by ask desc
  rownames(df) <- NULL
  utils::head(df, max_per_page * pages)
}

#' @export
discover_top_listings <- function(rarity = "Diamond",
                                  pages = 1L, max_per_page = 25L) {
  .theshow_init_cache()
  if (!is.function(.discover_memoised)) {
    .discover_memoised <<- memoise::memoise(
      discover_top_listings_uncached,
      cache = .theshow_cache
    )
  }
  .discover_memoised(rarity, pages, max_per_page)
}
.discover_memoised <- NULL

#' MLB Stats API client.
#'
#' Public, no auth: https://statsapi.mlb.com/api/v1/...
#' Used by the OVR predictor to fetch recent (14d) vs season splits.

.mlb_cache <- NULL

.mlb_init_cache <- function() {
  if (is.null(.mlb_cache)) {
    .mlb_cache <<- cachem::cache_mem(max_size = 32 * 1024^2, max_age = 3600)
  }
  invisible(NULL)
}

.mlb_get <- function(path, query = list(), timeout = 15) {
  req <- httr2::request("https://statsapi.mlb.com") |>
    httr2::req_url_path_append(path) |>
    httr2::req_url_query(!!!query) |>
    httr2::req_user_agent("mlbshowterminal/1.0") |>
    httr2::req_timeout(timeout) |>
    httr2::req_retry(max_tries = 3, backoff = function(i) 2^i)
  resp <- tryCatch(httr2::req_perform(req),
                   error = function(e) NULL)
  if (is.null(resp)) return(NULL)
  tryCatch(httr2::resp_body_json(resp, simplifyVector = FALSE),
           error = function(e) NULL)
}

#' First match from /people/search.
#' @export
mlb_search_player_uncached <- function(name) {
  q <- normalize_name(name)
  if (nchar(q) == 0L) return(NULL)
  body <- .mlb_get("/api/v1/people/search", list(names = q))
  ppl <- body$people
  if (is.null(ppl) || length(ppl) == 0L) return(NULL)
  p <- ppl[[1]]
  list(
    id = as.integer(p$id),
    full_name = p$fullName %||% p$nameFirstLast %||% NA_character_,
    primary_position = p$primaryPosition$name %||% NA_character_,
    primary_position_code = p$primaryPosition$code %||% NA_character_
  )
}

#' Memoised public entry point.
#' @export
mlb_search_player <- function(name) {
  .mlb_init_cache()
  if (!is.function(.mlb_search_player_memoised)) {
    .mlb_search_player_memoised <<- memoise::memoise(
      mlb_search_player_uncached, cache = .mlb_cache
    )
  }
  .mlb_search_player_memoised(name)
}
.mlb_search_player_memoised <- NULL

#' Player stats by date range. Returns a flat list of numeric stats.
#' @param id integer player id
#' @param start_date,end_date character "YYYY-MM-DD"
#' @param group "hitting" or "pitching"
#' @export
mlb_player_stats_uncached <- function(id, start_date, end_date,
                                      group = c("hitting", "pitching")) {
  group <- match.arg(group)
  body <- .mlb_get(
    sprintf("/api/v1/people/%d/stats", as.integer(id)),
    list(stats = "byDateRange", startDate = start_date,
         endDate = end_date, group = group)
  )
  if (is.null(body) || length(body$stats) == 0L) return(list())
  splits <- body$stats[[1]]$splits
  if (is.null(splits) || length(splits) == 0L) return(list())
  stat <- splits[[1]]$stat %||% list()
  # Coerce string stats to numeric
  out <- lapply(stat, function(v) {
    if (is.character(v)) suppressWarnings(as.numeric(v)) else v
  })
  out
}

#' Memoised public entry point.
#' @export
mlb_player_stats <- function(id, start_date, end_date,
                             group = c("hitting", "pitching")) {
  .mlb_init_cache()
  if (!is.function(.mlb_player_stats_memoised)) {
    .mlb_player_stats_memoised <<- memoise::memoise(
      mlb_player_stats_uncached, cache = .mlb_cache
    )
  }
  .mlb_player_stats_memoised(id, start_date, end_date, group)
}
.mlb_player_stats_memoised <- NULL

#' Convenience: fetch recent (14d) vs season-to-date splits in the shape the
#' OVR predictor expects.
#'
#' @param name character.
#' @param role NULL (auto-detect from primary_position) or "hitter"/"pitcher".
#' @param today Date (default Sys.Date()).
#' @return list(recent, season, role, player) — recent/season are flat
#'   lists with ops/avg/era/whip etc.; role is the resolved role.
#' @export
get_recent_vs_season_stats <- function(name, role = NULL,
                                       today = Sys.Date()) {
  player <- mlb_search_player(name)
  if (is.null(player)) {
    return(list(recent = list(), season = list(),
                role = role %||% "hitter", player = NULL))
  }
  if (is.null(role)) {
    role <- if (grepl("Pitcher", player$primary_position %||% "",
                      ignore.case = TRUE)) "pitcher" else "hitter"
  }
  group <- if (role == "pitcher") "pitching" else "hitting"
  end <- format(today, "%Y-%m-%d")
  recent_start <- format(today - 14L, "%Y-%m-%d")
  # Season start: MLB regular season conventional start ~ March 27.
  # Use Mar 1 of the current year for safety.
  season_start <- format(as.Date(sprintf("%d-03-01",
                                         as.integer(format(today, "%Y")))),
                         "%Y-%m-%d")
  recent <- mlb_player_stats(player$id, recent_start, end, group)
  season <- mlb_player_stats(player$id, season_start, end, group)
  list(recent = recent, season = season, role = role, player = player)
}

#' Force-clear memoise caches.
#' @export
mlb_clear_cache <- function() {
  if (!is.null(.mlb_cache)) .mlb_cache$reset()
  invisible(NULL)
}

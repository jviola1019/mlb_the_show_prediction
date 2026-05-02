#' Optional Anthropic LLM cross-check.
#'
#' Activated only when ANTHROPIC_API_KEY env var is set. Uses claude-opus-4-7
#' (latest as of 2026-05-02) with prompt caching on the system prompt. Caching
#' is keyed by the system block; re-runs within ~5 minutes pay no input
#' tokens for the system text.
#'
#' Always returns NULL on missing key or HTTP error — the caller must render
#' a graceful banner ("Set ANTHROPIC_API_KEY to enable") and never crash.

ANTHROPIC_MODEL <- "claude-opus-4-7"
ANTHROPIC_VERSION <- "2023-06-01"
ANTHROPIC_BETA_CACHE <- "prompt-caching-2024-07-31"

#' @export
anthropic_available <- function() {
  k <- Sys.getenv("ANTHROPIC_API_KEY", "")
  is.character(k) && nchar(k) > 0
}

#' Get a one-paragraph cross-check of a recommendation.
#'
#' @param card_meta list with name, rarity, ovr, team, series.
#' @param forecast_summary list with ev, p_profit, p_up, drift_p, hurst.
#' @param recommendation list (output of recommendation_score()).
#' @return character (one paragraph) or NULL on any failure.
#' @export
anthropic_card_summary <- function(card_meta, forecast_summary,
                                   recommendation) {
  if (!anthropic_available()) return(NULL)

  system_text <- paste0(
    "You are a sober quant analyst reviewing a card-market trade. ",
    "You are given the model's recommendation and supporting metrics. ",
    "Reply in ONE paragraph (<=100 words). State whether the recommendation ",
    "is consistent with the metrics, name the strongest supporting and ",
    "strongest contradicting signal, and end with one sentence on what ",
    "would change your mind. No hype, no hedging. No bullet points."
  )

  user_text <- sprintf(
    paste0("Card: %s | rarity=%s | ovr=%s | team=%s\n",
           "Recommendation: %s (score=%d)\n",
           "Forecast: 7d EV=%.1f%% | P(profit)=%.1f%% | P(up)=%.1f%% | ",
           "drift_p=%s | hurst=%.2f\n",
           "Flags: %s"),
    card_meta$name %||% "(unknown)",
    card_meta$rarity %||% "?",
    card_meta$ovr %||% "?",
    card_meta$team %||% "?",
    recommendation$action,
    recommendation$score,
    100 * (forecast_summary$ev %||% 0),
    100 * (forecast_summary$p_profit %||% 0),
    100 * (forecast_summary$p_up %||% 0),
    if (is.na(forecast_summary$drift_p %||% NA)) "NA"
      else sprintf("%.3f", forecast_summary$drift_p),
    forecast_summary$hurst %||% NA_real_,
    paste(vapply(recommendation$flags %||% list(),
                 function(f) f$text %||% "", character(1)),
          collapse = ", ")
  )

  body <- list(
    model = ANTHROPIC_MODEL,
    max_tokens = 400L,
    system = list(list(
      type = "text",
      text = system_text,
      cache_control = list(type = "ephemeral")
    )),
    messages = list(list(
      role = "user",
      content = list(list(type = "text", text = user_text))
    ))
  )

  req <- httr2::request("https://api.anthropic.com/v1/messages") |>
    httr2::req_method("POST") |>
    httr2::req_headers(
      `x-api-key` = Sys.getenv("ANTHROPIC_API_KEY"),
      `anthropic-version` = ANTHROPIC_VERSION,
      `anthropic-beta` = ANTHROPIC_BETA_CACHE,
      `content-type` = "application/json"
    ) |>
    httr2::req_body_json(body) |>
    httr2::req_timeout(30) |>
    httr2::req_retry(max_tries = 2)

  resp <- tryCatch(httr2::req_perform(req), error = function(e) NULL)
  if (is.null(resp)) return(NULL)
  if (httr2::resp_status(resp) >= 400) return(NULL)

  parsed <- tryCatch(
    httr2::resp_body_json(resp, simplifyVector = FALSE),
    error = function(e) NULL
  )
  if (is.null(parsed) || length(parsed$content) == 0L) return(NULL)
  txt <- parsed$content[[1]]$text
  if (is.null(txt) || !nchar(txt)) return(NULL)
  txt
}

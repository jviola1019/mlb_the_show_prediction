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
#' @param verdict optional list (output of `gating_verdict()`); if NULL, the
#'   LLM is told no verdict context was supplied.
#' @param gates optional named list (output of `validation_gates()`).
#' @return character (one paragraph) or NULL on any failure.
#' @export
anthropic_card_summary <- function(card_meta, forecast_summary,
                                   recommendation,
                                   verdict = NULL, gates = NULL) {
  if (!anthropic_available()) return(NULL)

  system_text <- paste0(
    "You are a sober quant analyst reviewing a card-market trade. ",
    "You are given the model's recommendation, supporting metrics, AND the ",
    "exact verdict + failed-gate names from the upstream statistical ",
    "validation layer. Reply in ONE paragraph (<=120 words). ",
    "If the verdict is NOT INVESTABLE, your paragraph must open by ",
    "explaining which named gates failed and why that means the user ",
    "cannot act on this card; do not estimate EV or direction. ",
    "If the verdict is OBSERVATIONAL ONLY, describe the direction and the ",
    "reason the model can only observe (e.g. negative-skill CV, wide CIs). ",
    "If the verdict is INVESTABLE, name the strongest supporting and ",
    "strongest contradicting signal. End with one sentence on what would ",
    "change your read. No hype, no hedging, no bullet points. ",
    "CRITICAL: Your output is COMMENTARY, NOT a trading signal. Never tell ",
    "the user what to do; describe what the metrics imply. The statistical ",
    "validation gates upstream of you have final authority — your role is ",
    "interpretation only."
  )

  failed_gates_csv <- if (!is.null(verdict)) {
    paste(verdict$failed %||% character(0), collapse = ", ")
  } else "(no verdict supplied)"
  failed_reasons <- if (!is.null(verdict) && length(verdict$reasons %||% c()) > 0L) {
    paste(verdict$reasons, collapse = " | ")
  } else "(none)"
  verdict_status <- if (!is.null(verdict)) verdict$status %||% "(unknown)"
                    else "(no verdict supplied)"
  cv_skill_pass <- if (!is.null(gates) && !is.null(gates$cv_skill_not_negative_sig))
                     gates$cv_skill_not_negative_sig$passed else NA
  cal_pass <- if (!is.null(gates) && !is.null(gates$calibration_present))
                gates$calibration_present$passed else NA

  user_text <- sprintf(
    paste0("Card: %s | rarity=%s | ovr=%s | team=%s\n",
           "Verdict: %s\n",
           "Failed gates: %s\n",
           "Failure reasons: %s\n",
           "Recommendation: %s (score=%s)\n",
           "Forecast: 7d EV=%.1f%% | P(profit)=%.1f%% | P(up)=%.1f%% | ",
           "drift_p=%s | hurst=%.2f\n",
           "CV skill gate passed: %s | calibration gate passed: %s\n",
           "Flags: %s"),
    card_meta$name %||% "(unknown)",
    card_meta$rarity %||% "?",
    card_meta$ovr %||% "?",
    card_meta$team %||% "?",
    verdict_status,
    failed_gates_csv,
    failed_reasons,
    recommendation$action %||% "(none)",
    if (is.na(recommendation$score %||% NA)) "NA"
      else as.character(recommendation$score),
    100 * (forecast_summary$ev %||% 0),
    100 * (forecast_summary$p_profit %||% 0),
    100 * (forecast_summary$p_up %||% 0),
    if (is.na(forecast_summary$drift_p %||% NA)) "NA"
      else sprintf("%.3f", forecast_summary$drift_p),
    forecast_summary$hurst %||% NA_real_,
    if (is.na(cv_skill_pass)) "unknown" else if (cv_skill_pass) "yes" else "no",
    if (is.na(cal_pass)) "unknown" else if (cal_pass) "yes" else "no",
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

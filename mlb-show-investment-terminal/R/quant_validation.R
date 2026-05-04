#' Statistical validation gates.
#'
#' The CARD tab should never publish an action verb (BUY / SELL / etc.) when
#' the underlying analysis cannot support it. These gates encode the
#' minimum bar. Any failed gate downgrades or suppresses the recommendation.
#'
#' Six gates, in order of severity:
#'   1. schema_valid              — listing has required fields and a valid UUID.
#'   2. history_sufficient        — enough price points for a stable bootstrap.
#'   3. data_fresh                — most recent tick within 48h.
#'   4. cv_available              — walk-forward CV produced >= 30 trades.
#'   5. cv_skill_not_negative_sig — CV IC upper-CI bound >= 0 (no sig anti-skill).
#'   6. ci_width_acceptable       — Brier CI width <= 0.20 AND IC CI width <= 0.50.
#'
#' Verdict tiers:
#'   - INVESTABLE         — all 6 gates pass; full recommendation shown.
#'   - OBSERVATIONAL ONLY — gates 1–4 pass; 5 or 6 fails. Direction shown,
#'                         action verb suppressed.
#'   - NOT INVESTABLE     — any of gates 1–4 fails. Action verb suppressed,
#'                         EV table blanked, ABSTAIN verdict.

#' Compute the seven gates.
#'
#' Gate 7 (calibration_present) is checked when the caller supplies a
#' `calibration_ok` argument. Default TRUE so older call sites that don't
#' yet pass it remain backwards-compatible at the same governance level
#' as before.
#'
#' @param price_history data.frame (timestamp, price), or NULL.
#' @param listing list (`get_listing()` output) or NULL.
#' @param wfcv list (`walk_forward_cv()` output) or NULL.
#' @param horizon integer.
#' @param calibration_ok logical; did isotonic calibration run cleanly?
#' @param now POSIXct (default Sys.time()).
#' @return named list of `list(passed = logical, reason = character)`.
#' @export
validation_gates <- function(price_history, listing, wfcv, horizon = 7L,
                             calibration_ok = TRUE,
                             now = Sys.time()) {
  gate <- function(passed, reason = "") {
    list(passed = isTRUE(passed), reason = if (passed) "ok" else reason)
  }

  # Gate 1: schema
  schema_ok <- !is.null(listing) &&
    !is.null(listing$item) &&
    is_valid_uuid(listing$item$uuid %||% "") &&
    isTRUE((listing$best_sell_price %||% 0) > 0) &&
    isTRUE((listing$best_buy_price %||% 0) > 0) &&
    length(listing$completed_orders %||% list()) >= 8L
  schema_reason <- if (schema_ok) "ok" else
    "listing missing required fields or completed_orders < 8"

  # Gate 2: history sufficient
  hist_n <- if (!is.null(price_history)) nrow(price_history) else 0L
  needed <- max(50L, 6L * horizon)
  hist_ok <- hist_n >= needed
  hist_reason <- if (hist_ok) "ok" else
    sprintf("only %d price points (need %d for horizon=%d)",
            hist_n, needed, horizon)

  # Gate 3: data freshness
  fresh_ok <- FALSE
  fresh_reason <- "no price history"
  if (!is.null(price_history) && nrow(price_history) > 0L) {
    age_h <- as.numeric(difftime(now, max(price_history$timestamp),
                                 units = "hours"))
    fresh_ok <- is.finite(age_h) && age_h <= 48
    fresh_reason <- if (fresh_ok) "ok" else
      sprintf("most recent tick is %.1fh old (>48h)", age_h)
  }

  # Gate 4: CV availability
  cv_n <- if (!is.null(wfcv)) wfcv$n_trades %||% 0L else 0L
  cv_ok <- !is.null(wfcv) && cv_n >= 30L
  cv_reason <- if (cv_ok) "ok" else
    sprintf("walk-forward CV unavailable or n_trades=%d (<30)", cv_n)

  # Gate 5: skill not significantly negative
  skill_ok <- TRUE
  skill_reason <- "ok"
  if (!is.null(wfcv) && length(wfcv$ic_ci) == 2L &&
      is.finite(wfcv$ic_ci[2])) {
    skill_ok <- wfcv$ic_ci[2] >= 0
    if (!skill_ok) {
      skill_reason <- sprintf(
        "CV IC upper bound = %+.2f (significant negative skill)",
        wfcv$ic_ci[2])
    }
  } else if (!cv_ok) {
    skill_ok <- FALSE
    skill_reason <- "CV unavailable; cannot evaluate skill"
  }

  # Gate 6: CI width acceptable
  width_ok <- TRUE
  width_reason <- "ok"
  if (!is.null(wfcv)) {
    bw <- if (length(wfcv$brier_ci) == 2L && all(is.finite(wfcv$brier_ci)))
            diff(wfcv$brier_ci) else NA_real_
    iw <- if (length(wfcv$ic_ci) == 2L && all(is.finite(wfcv$ic_ci)))
            diff(wfcv$ic_ci) else NA_real_
    width_ok <- is.finite(bw) && bw <= 0.20 &&
                is.finite(iw) && iw <= 0.50
    if (!width_ok) {
      width_reason <- sprintf(
        "CI too wide (Brier width=%.2f, IC width=%.2f; cap 0.20/0.50)",
        bw %||% NA_real_, iw %||% NA_real_)
    }
  } else if (!cv_ok) {
    width_ok <- FALSE
    width_reason <- "CV unavailable; cannot evaluate CI width"
  }

  # Gate 7: calibration improves out-of-sample Brier.
  # `calibration_ok` may be a bare logical (older callers) OR a list of the
  # shape returned by `calibration_held_out_check()`. The richer form lets
  # us print the actual Brier delta in the failure reason.
  if (is.list(calibration_ok)) {
    cal_ok     <- isTRUE(calibration_ok$ok)
    cal_reason <- calibration_ok$reason %||% (if (cal_ok) "ok" else
      "isotonic calibration did not improve held-out Brier")
  } else {
    cal_ok <- isTRUE(calibration_ok)
    cal_reason <- if (cal_ok) "ok" else
      "isotonic calibration unavailable or did not improve held-out Brier"
  }

  list(
    schema_valid              = gate(schema_ok,  schema_reason),
    history_sufficient        = gate(hist_ok,    hist_reason),
    data_fresh                = gate(fresh_ok,   fresh_reason),
    cv_available              = gate(cv_ok,      cv_reason),
    cv_skill_not_negative_sig = gate(skill_ok,   skill_reason),
    ci_width_acceptable       = gate(width_ok,   width_reason),
    calibration_present       = gate(cal_ok,     cal_reason)
  )
}

#' Map gate results to a verdict.
#' Calibration absence (gate 7) is treated as a soft failure — the
#' bootstrap can still report direction, but staking math and Kelly
#' fractions should not be published without calibrated probabilities.
#' @export
gating_verdict <- function(gates) {
  hard_keys <- c("schema_valid", "history_sufficient", "data_fresh",
                 "cv_available")
  soft_keys <- c("cv_skill_not_negative_sig", "ci_width_acceptable",
                 "calibration_present")
  # Tolerate older callers that don't supply the calibration gate.
  soft_keys <- soft_keys[soft_keys %in% names(gates)]
  hard_pass <- all(vapply(gates[hard_keys], function(g) g$passed, logical(1)))
  soft_pass <- all(vapply(gates[soft_keys], function(g) g$passed, logical(1)))
  failed <- names(gates)[!vapply(gates, function(g) g$passed, logical(1))]
  reasons <- vapply(gates[failed], function(g) g$reason, character(1))

  if (!hard_pass) {
    list(status = "NOT INVESTABLE", badge_tone = "bear",
         headline = "ABSTAIN — INSUFFICIENT VALIDATION",
         reasons = reasons, failed = failed)
  } else if (!soft_pass) {
    list(status = "OBSERVATIONAL ONLY", badge_tone = "warn",
         headline = "OBSERVATIONAL ONLY — direction reported, no action",
         reasons = reasons, failed = failed)
  } else {
    list(status = "INVESTABLE", badge_tone = "bull",
         headline = "INVESTABLE — all 7 gates passed",
         reasons = character(0), failed = character(0))
  }
}

#' One pill per gate; pass = bull (✓), fail = bear (✗ + reason).
#' @export
gates_summary_pills <- function(gates) {
  short_names <- c(
    schema_valid              = "SCHEMA",
    history_sufficient        = "HISTORY",
    data_fresh                = "FRESHNESS",
    cv_available              = "CV AVAILABLE",
    cv_skill_not_negative_sig = "CV SKILL",
    ci_width_acceptable       = "CI WIDTH",
    calibration_present       = "CALIBRATION"
  )
  htmltools::tags$div(
    class = "gates-panel",
    lapply(names(gates), function(k) {
      g <- gates[[k]]
      tone <- if (g$passed) "bull" else "bear"
      mark <- if (g$passed) "✓" else "✗"
      htmltools::tags$div(
        class = "gate-row",
        htmltools::tags$span(
          class = paste("pill", paste0("pill-", tone)),
          paste(mark, short_names[[k]] %||% toupper(k))
        ),
        if (!g$passed) htmltools::tags$span(class = "gate-reason",
                                            g$reason) else NULL
      )
    })
  )
}

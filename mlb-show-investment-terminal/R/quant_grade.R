#' Tier grading — sub-classifies the verdict tiers into the
#' DIAMOND / GOLD / SILVER / BRONZE / ABSTAIN scheme.
#'
#' This does NOT relax any gate. It only stratifies INVESTABLE into
#' DIAMOND vs GOLD (based on conviction-quality criteria) and splits
#' NOT INVESTABLE into BRONZE (recoverable: thin data) vs ABSTAIN
#' (hard: bad schema or stale).

#' Compute the tier from the verdict + gate set + supporting metrics.
#'
#' DIAMOND criteria (all must hold; verdict must be INVESTABLE):
#'   * `wfcv$ic_ci[1] >= 0.05`           (lower CI bound on IC is positive)
#'   * `diff(wfcv$brier_ci) <= 0.10`     (tight Brier CI)
#'   * `liquidity_score >= 0.7`          (deep market)
#'   * `holdout_brier_delta <= -0.005`   (calibration measurably improves)
#'
#' GOLD: INVESTABLE but not DIAMOND.
#' SILVER: OBSERVATIONAL ONLY.
#' BRONZE: NOT INVESTABLE due to history_sufficient OR cv_available
#'   failing AND schema_valid + data_fresh both passing — recoverable
#'   ("come back when we have more data").
#' ABSTAIN: NOT INVESTABLE due to schema_valid OR data_fresh failing —
#'   data-quality block; not recoverable on this card right now.
#'
#' @param verdict list (output of `gating_verdict()`).
#' @param gates list (output of `validation_gates()`).
#' @param liquidity_score numeric in [0, 1] (from `liquidity_score()$score`).
#' @param wfcv list (output of `walk_forward_cv()`) or NULL.
#' @param holdout_brier_delta numeric (from `calibration_held_out_check()$delta`).
#' @return list(tier, label, tone, reason).
#' @export
tier_grade <- function(verdict, gates,
                       liquidity_score = NA_real_,
                       wfcv = NULL,
                       holdout_brier_delta = NA_real_) {
  status <- verdict$status %||% "(unknown)"

  if (status == "INVESTABLE") {
    ic_lo <- if (!is.null(wfcv) && length(wfcv$ic_ci) == 2L)
      wfcv$ic_ci[1] else NA_real_
    brier_w <- if (!is.null(wfcv) && length(wfcv$brier_ci) == 2L)
      diff(wfcv$brier_ci) else NA_real_

    diamond <- isTRUE(is.finite(ic_lo) && ic_lo >= 0.05) &&
               isTRUE(is.finite(brier_w) && brier_w <= 0.10) &&
               isTRUE(is.finite(liquidity_score) && liquidity_score >= 0.7) &&
               isTRUE(is.finite(holdout_brier_delta) &&
                      holdout_brier_delta <= -0.005)
    if (diamond) {
      return(list(tier = "DIAMOND", label = "DIAMOND",
                  tone = "diamond",
                  reason = sprintf(
                    "IC lower CI=%.2f, Brier width=%.2f, liquidity=%.2f, cal delta=%.3f",
                    ic_lo, brier_w, liquidity_score, holdout_brier_delta)))
    }
    return(list(tier = "GOLD", label = "GOLD",
                tone = "gold",
                reason = "all gates pass; sub-DIAMOND criteria"))
  }

  if (status == "OBSERVATIONAL ONLY") {
    return(list(tier = "SILVER", label = "SILVER",
                tone = "silver",
                reason = paste("observational; failed gates:",
                               paste(verdict$failed %||% character(0),
                                     collapse = ", "))))
  }

  if (status == "NOT INVESTABLE") {
    schema_pass <- isTRUE(gates$schema_valid$passed)
    fresh_pass  <- isTRUE(gates$data_fresh$passed)
    hist_fail   <- !isTRUE(gates$history_sufficient$passed)
    cv_fail     <- !isTRUE(gates$cv_available$passed)
    if (schema_pass && fresh_pass && (hist_fail || cv_fail)) {
      return(list(tier = "BRONZE", label = "BRONZE",
                  tone = "bronze",
                  reason = "data sparse; schema + freshness OK — recheck after more trades"))
    }
    return(list(tier = "ABSTAIN", label = "ABSTAIN",
                tone = "abstain",
                reason = paste("hard data-quality block:",
                               paste(verdict$failed %||% character(0),
                                     collapse = ", "))))
  }

  list(tier = "UNKNOWN", label = "UNKNOWN", tone = "neutral",
       reason = sprintf("unrecognised verdict status: %s", status))
}

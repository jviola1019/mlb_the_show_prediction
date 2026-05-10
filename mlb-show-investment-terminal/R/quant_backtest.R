#' Historical roster-update backtest helpers.
#'
#' These functions evaluate real historical labels when they are supplied.
#' They never fabricate labels or persist local state.

.parse_binary_outcome <- function(x) {
  if (is.logical(x)) return(as.integer(x))
  if (is.numeric(x)) return(as.integer(x > 0))
  sx <- tolower(trimws(as.character(x)))
  as.integer(sx %in% c("1", "true", "upgraded", "upgrade", "crossed",
                       "crossed_next_threshold", "yes"))
}

#' Evaluate threshold prediction calibration against historical labels.
#'
#' @param predictions data.frame with UUID/probability columns, or a combined
#'   frame that also contains the outcome.
#' @param labels optional data.frame with matching UUID/outcome columns.
#' @return list(status, metrics, calibration_curve, reason).
#' @export
upgrade_backtest_metrics <- function(predictions = NULL, labels = NULL,
                                     uuid_col = "uuid",
                                     prob_col = "p_cross_next_threshold",
                                     outcome_col = "crossed_next_threshold",
                                     n_bins = 5L) {
  unavailable <- function(reason) {
    list(status = "unavailable", reason = reason,
         n = 0L, brier_score = NA_real_, precision = NA_real_,
         recall = NA_real_,
         calibration_curve = reliability_diagram_data(numeric(0), integer(0),
                                                      n_bins = n_bins))
  }

  if (is.null(predictions) || !is.data.frame(predictions) ||
      nrow(predictions) == 0L) {
    return(unavailable("no historical prediction rows supplied"))
  }

  df <- predictions
  if (!outcome_col %in% names(df)) {
    if (is.null(labels) || !is.data.frame(labels) || nrow(labels) == 0L) {
      return(unavailable("no historical roster-update labels supplied"))
    }
    if (!uuid_col %in% names(df) || !uuid_col %in% names(labels) ||
        !outcome_col %in% names(labels)) {
      return(unavailable("labels must include uuid and outcome columns"))
    }
    df <- merge(df, labels[, c(uuid_col, outcome_col), drop = FALSE],
                by = uuid_col, all = FALSE)
  }

  if (!prob_col %in% names(df) || !outcome_col %in% names(df)) {
    return(unavailable("probability or outcome column missing"))
  }

  p <- suppressWarnings(as.numeric(df[[prob_col]]))
  y <- .parse_binary_outcome(df[[outcome_col]])
  ok <- is.finite(p) & !is.na(y)
  p <- .clamp01(p[ok])
  y <- y[ok]
  if (length(p) == 0L) {
    return(unavailable("no rows with finite probabilities and labels"))
  }

  pred_pos <- p >= 0.5
  y_pos <- y == 1L
  tp <- sum(pred_pos & y_pos)
  fp <- sum(pred_pos & !y_pos)
  fn <- sum(!pred_pos & y_pos)

  list(
    status = "ok",
    reason = "historical labels evaluated",
    n = length(p),
    brier_score = brier_score(p, y),
    precision = if ((tp + fp) > 0L) tp / (tp + fp) else NA_real_,
    recall = if ((tp + fn) > 0L) tp / (tp + fn) else NA_real_,
    calibration_curve = reliability_diagram_data(p, y, n_bins = n_bins)
  )
}

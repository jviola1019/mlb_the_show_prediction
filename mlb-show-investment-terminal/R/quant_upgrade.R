#' Roster upgrade / OVR threshold engine.
#'
#' The engine reports threshold probabilities and distance-to-threshold.
#' Exact delta-OVR remains a diagnostic, not the decision surface.

.clamp01 <- function(x) pmin(1, pmax(0, as.numeric(x)))
.clamp100 <- function(x) pmin(100, pmax(0, as.numeric(x)))

.safe_num <- function(x) {
  if (is.null(x) || length(x) == 0L) return(NA_real_)
  suppressWarnings(as.numeric(x[[1L]]))
}

#' Next economically relevant OVR threshold by rarity/current OVR.
#' @export
next_ovr_threshold <- function(current_ovr, rarity = NULL) {
  ovr <- .safe_num(current_ovr)
  if (!is.finite(ovr)) return(NA_real_)
  r <- tolower(as.character(rarity %||% ""))

  if (grepl("common", r, fixed = TRUE) || ovr < 65) return(65)
  if (grepl("bronze", r, fixed = TRUE) || (ovr >= 65 && ovr < 75)) return(75)
  if (grepl("silver", r, fixed = TRUE) || (ovr >= 75 && ovr < 80)) return(80)
  if (grepl("gold", r, fixed = TRUE) || (ovr >= 80 && ovr < 85)) return(85)
  if (grepl("diamond", r, fixed = TRUE) || ovr >= 85) {
    if (ovr < 90) return(90)
    if (ovr < 95) return(95)
    return(NA_real_)
  }
  NA_real_
}

#' Rarity-aware distance to the next OVR threshold.
#' @export
distance_to_ovr_threshold <- function(current_ovr, rarity = NULL) {
  ovr <- .safe_num(current_ovr)
  thr <- next_ovr_threshold(ovr, rarity)
  if (!is.finite(ovr) || !is.finite(thr)) return(NA_real_)
  max(0, thr - ovr)
}

#' Distance to a fixed OVR threshold.
#' @export
distance_to_ovr <- function(current_ovr, threshold) {
  ovr <- .safe_num(current_ovr)
  threshold <- .safe_num(threshold)
  if (!is.finite(ovr) || !is.finite(threshold)) return(NA_real_)
  max(0, threshold - ovr)
}

.required_z_for_delta <- function(delta_required) {
  d <- ceiling(.safe_num(delta_required))
  if (!is.finite(d) || d <= 0) return(NA_real_)
  if (d == 1L) return(0.5)
  if (d == 2L) return(1.2)
  if (d == 3L) return(2.0)
  NA_real_
}

.prob_delta_at_least <- function(z, delta_required, z_sd) {
  z_req <- .required_z_for_delta(delta_required)
  if (!is.finite(z) || !is.finite(z_req) || !is.finite(z_sd) || z_sd <= 0) {
    return(NA_real_)
  }
  stats::pnorm(z_req, mean = z, sd = z_sd, lower.tail = FALSE)
}

.playing_time_score <- function(stats_recent, stats_season, role) {
  role <- match.arg(role, c("hitter", "pitcher"))
  if (role == "hitter") {
    recent <- .safe_num(stats_recent$plateAppearances %||%
                          stats_recent$pa %||% stats_recent$atBats)
    season <- .safe_num(stats_season$plateAppearances %||%
                          stats_season$pa %||% stats_season$atBats)
    if (!is.finite(recent) && !is.finite(season)) {
      return(list(score = 0, ok = FALSE, reason = "PLAYING_TIME_UNAVAILABLE"))
    }
    recent_v <- if (is.finite(recent)) recent else 0
    season_v <- if (is.finite(season)) season else 0
    score <- min(1, (max(0, recent_v) / 20) * 0.6 +
                   (max(0, season_v) / 80) * 0.4)
    return(list(score = score, ok = score >= 0.5,
                reason = if (score >= 0.5) "PLAYING_TIME_OK" else
                  "PLAYING_TIME_LOW"))
  }

  recent <- .safe_num(stats_recent$inningsPitched %||% stats_recent$ip)
  season <- .safe_num(stats_season$inningsPitched %||% stats_season$ip)
  if (!is.finite(recent) && !is.finite(season)) {
    return(list(score = 0, ok = FALSE, reason = "PLAYING_TIME_UNAVAILABLE"))
  }
  recent_v <- if (is.finite(recent)) recent else 0
  season_v <- if (is.finite(season)) season else 0
  score <- min(1, (max(0, recent_v) / 5) * 0.6 +
                 (max(0, season_v) / 25) * 0.4)
  list(score = score, ok = score >= 0.5,
       reason = if (score >= 0.5) "PLAYING_TIME_OK" else "PLAYING_TIME_LOW")
}

.threshold_cross_prob <- function(current_ovr, threshold, z, z_sd) {
  ovr <- .safe_num(current_ovr)
  threshold <- .safe_num(threshold)
  if (!is.finite(ovr) || !is.finite(threshold)) return(NA_real_)
  if (ovr >= threshold) return(NA_real_)
  .prob_delta_at_least(z, threshold - ovr, z_sd)
}

.recent_delta_text <- function(stats_recent, stats_season, role) {
  role <- match.arg(role, c("hitter", "pitcher"))
  if (role == "hitter") {
    ops_d <- .safe_num(stats_recent$ops) - .safe_num(stats_season$ops)
    avg_d <- .safe_num(stats_recent$avg) - .safe_num(stats_season$avg)
    return(sprintf("OPS %+.3f; AVG %+.3f", ops_d, avg_d))
  }
  era_d <- .safe_num(stats_recent$era) - .safe_num(stats_season$era)
  whip_d <- .safe_num(stats_recent$whip) - .safe_num(stats_season$whip)
  sprintf("ERA %+.2f; WHIP %+.2f", era_d, whip_d)
}

#' Compute roster-upgrade probabilities and recommendation.
#'
#' @return list with probabilities, threshold distance, confidence, action,
#'   score, exact delta diagnostic, and reason codes.
#' @export
roster_upgrade_engine <- function(stats_recent, stats_season, role,
                                  current_ovr, rarity,
                                  new_rank = NA_real_) {
  role <- match.arg(role, c("hitter", "pitcher"))
  current_ovr <- .safe_num(current_ovr)
  new_rank <- .safe_num(new_rank)
  next_threshold <- next_ovr_threshold(current_ovr, rarity)
  distance <- distance_to_ovr_threshold(current_ovr, rarity)
  distance_85 <- distance_to_ovr(current_ovr, 85)
  distance_90 <- distance_to_ovr(current_ovr, 90)
  reasons <- c("UNCALIBRATED_THRESHOLD_MODEL")

  zr <- ovr_z_score(stats_recent, stats_season, role = role)
  components <- zr$components
  has_stats <- length(components) > 0L && is.finite(zr$z)
  pt <- .playing_time_score(stats_recent, stats_season, role)
  reasons <- c(reasons, pt$reason)
  if (!has_stats) reasons <- c(reasons, "RECENT_STATS_UNAVAILABLE")

  z <- if (has_stats) zr$z else 0
  z_sd <- if (pt$ok) 0.85 else 1.10
  p_upgrade <- if (has_stats) .prob_delta_at_least(z, 1, z_sd) else NA_real_
  p_downgrade <- if (has_stats) stats::pnorm(-0.5, mean = z, sd = z_sd) else NA_real_
  p_cross_next <- if (has_stats && is.finite(distance) && distance > 0) {
    .prob_delta_at_least(z, distance, z_sd)
  } else if (has_stats && is.finite(distance) && distance == 0) {
    1
  } else NA_real_
  p_cross_85 <- if (has_stats) .threshold_cross_prob(current_ovr, 85, z, z_sd)
                else NA_real_
  p_cross_90 <- if (has_stats) .threshold_cross_prob(current_ovr, 90, z, z_sd)
                else NA_real_

  if (is.finite(distance) && distance > 3) {
    p_cross_next <- 0
    reasons <- c(reasons, "THRESHOLD_BEYOND_ONE_UPDATE_MODEL")
  }

  new_rank_up <- is.finite(new_rank) && is.finite(current_ovr) &&
    new_rank > current_ovr
  new_rank_down <- is.finite(new_rank) && is.finite(current_ovr) &&
    new_rank < current_ovr
  new_rank_crosses_next <- new_rank_up && is.finite(next_threshold) &&
    current_ovr < next_threshold && new_rank >= next_threshold
  if (is.finite(new_rank)) {
    reasons <- c(reasons, "NEW_RANK_AVAILABLE")
    if (new_rank_up) reasons <- c(reasons, "NEW_RANK_UP")
    if (new_rank_down) reasons <- c(reasons, "NEW_RANK_DOWN")
    if (new_rank_crosses_next) reasons <- c(reasons, "NEW_RANK_CROSSES_THRESHOLD")
  } else {
    reasons <- c(reasons, "NEW_RANK_UNAVAILABLE")
  }

  if (new_rank_up) {
    p_upgrade <- max(p_upgrade %||% NA_real_, 0.70, na.rm = TRUE)
  }
  if (new_rank_down) {
    p_downgrade <- max(p_downgrade %||% NA_real_, 0.70, na.rm = TRUE)
  }
  if (new_rank_crosses_next) {
    p_cross_next <- max(p_cross_next %||% NA_real_, 0.85, na.rm = TRUE)
    if (current_ovr < 85 && next_threshold == 85) {
      p_cross_85 <- max(p_cross_85 %||% NA_real_, 0.85, na.rm = TRUE)
    }
    if (current_ovr < 90 && next_threshold == 90) {
      p_cross_90 <- max(p_cross_90 %||% NA_real_, 0.85, na.rm = TRUE)
    }
  }

  component_bonus <- min(length(components), 2L) / 2
  confidence <- .clamp100(
    25 + 25 * min(1, abs(z) / 2) +
      20 * pt$score +
      15 * component_bonus +
      if (is.finite(new_rank)) 15 else 0
  )
  if (new_rank_crosses_next) confidence <- max(confidence, 65)
  if (!has_stats && !is.finite(new_rank)) confidence <- 0

  proximity_bonus <- if (is.finite(distance)) {
    if (distance <= 1) 20 else if (distance == 2) 12 else if (distance == 3) 5 else 0
  } else 0
  upgrade_score <- .clamp100(
    45 * (p_cross_next %||% 0) +
      20 * (p_upgrade %||% 0) +
      0.15 * confidence +
      proximity_bonus -
      20 * (p_downgrade %||% 0)
  )

  action <- "HOLD"
  if (!has_stats && !is.finite(new_rank)) {
    action <- "AVOID"
  } else if (is.finite(p_downgrade) && p_downgrade >= 0.60 &&
             (!is.finite(p_upgrade) || p_upgrade < 0.40)) {
    action <- "SELL"
  } else if (new_rank_crosses_next && confidence >= 50) {
    action <- "BUY SPECULATIVE"
  } else if (is.finite(p_cross_next) && p_cross_next >= 0.55 &&
             confidence >= 65 && is.finite(distance) && distance <= 2) {
    action <- "BUY SPECULATIVE"
  } else if ((is.finite(p_upgrade) && p_upgrade >= 0.55) ||
             (is.finite(p_cross_next) && p_cross_next >= 0.25)) {
    action <- "WATCH"
  }

  if (action == "BUY SPECULATIVE") reasons <- c(reasons, "UPGRADE_EDGE")
  if (action == "WATCH") reasons <- c(reasons, "UPGRADE_WATCH")
  if (action == "SELL") reasons <- c(reasons, "DOWNGRADE_RISK")

  list(
    current_ovr = current_ovr,
    rarity = rarity,
    new_rank = new_rank,
    next_threshold = next_threshold,
    distance_to_threshold = distance,
    distance_to_85 = distance_85,
    distance_to_90 = distance_90,
    p_upgrade = .clamp01(p_upgrade),
    p_downgrade = .clamp01(p_downgrade),
    p_cross_next_threshold = .clamp01(p_cross_next),
    p_cross_85 = .clamp01(p_cross_85),
    p_cross_90 = .clamp01(p_cross_90),
    confidence = confidence,
    confidence_label = if (confidence >= 70) "high" else
      if (confidence >= 45) "medium" else "low",
    recent_vs_season_delta = .recent_delta_text(stats_recent, stats_season, role),
    exact_delta_ovr = z_to_delta_ovr(z),
    z = z,
    components = components,
    upgrade_score = upgrade_score,
    action = action,
    reason_codes = unique(reasons),
    reason_codes_csv = .join_reason_codes(reasons)
  )
}

#' OVR change predictor from MLB stats deltas.
#'
#' Hitter signal: average z-score of OPS_14d and BA_14d deltas.
#' Pitcher signal: average sign-flipped z-score of ERA and WHIP deltas.
#' Map weighted z to ΔOVR, then to ΔPrice% via rarity-band multipliers with
#' threshold jumps at OVR 75 / 80 / 85 (Bronze→Silver→Gold→Diamond).

# Standard deviations on 14-day stats (v3.3 calibration)
.OVR_STDS <- list(
  ops_14d  = 0.110,
  ba_14d   = 0.045,
  era_14d  = 1.20,
  whip_14d = 0.20
)

#' Compute z-score from recent vs season splits.
#' @param stats_recent named list with ops/avg or era/whip etc.
#' @param stats_season same shape.
#' @param role "hitter" or "pitcher".
#' @return list(z = numeric, components = named numeric).
#' @export
ovr_z_score <- function(stats_recent, stats_season,
                        role = c("hitter", "pitcher")) {
  role <- match.arg(role)
  components <- numeric(0)
  if (role == "hitter") {
    if (!is.null(stats_recent$ops) && !is.null(stats_season$ops)) {
      components["ops"] <- (as.numeric(stats_recent$ops) -
                              as.numeric(stats_season$ops)) / .OVR_STDS$ops_14d
    }
    if (!is.null(stats_recent$avg) && !is.null(stats_season$avg)) {
      components["ba"]  <- (as.numeric(stats_recent$avg) -
                              as.numeric(stats_season$avg)) / .OVR_STDS$ba_14d
    }
  } else {
    if (!is.null(stats_recent$era) && !is.null(stats_season$era)) {
      components["era"]  <- (as.numeric(stats_season$era) -
                               as.numeric(stats_recent$era)) /
        .OVR_STDS$era_14d  # sign-flipped
    }
    if (!is.null(stats_recent$whip) && !is.null(stats_season$whip)) {
      components["whip"] <- (as.numeric(stats_season$whip) -
                               as.numeric(stats_recent$whip)) /
        .OVR_STDS$whip_14d
    }
  }
  components <- components[is.finite(components)]
  z <- if (length(components) > 0L) mean(components) else 0
  list(z = z, components = components)
}

#' Map z to ΔOVR per v3.3 binning.
#' @export
z_to_delta_ovr <- function(z) {
  if (is.na(z) || !is.finite(z)) return(0L)
  if (z >  2)   return(3L)
  if (z >  1.2) return(2L)
  if (z >  0.5) return(1L)
  if (z < -2)   return(-3L)
  if (z < -1.2) return(-2L)
  if (z < -0.5) return(-1L)
  0L
}

#' Per-OVR ΔPrice% by rarity band.
#' @export
rarity_pct_per_ovr <- function(rarity) {
  if (is.null(rarity) || is.na(rarity)) return(0)
  r <- tolower(rarity)
  if (grepl("diamond", r)) return(0.15)
  if (grepl("gold", r))    return(0.20)
  if (grepl("silver", r))  return(0.10)
  if (grepl("bronze", r))  return(0.05)
  0
}

#' Detect rarity-band boundary jumps (Bronze→Silver at 75, Silver→Gold at 80,
#' Gold→Diamond at 85). Per v3.3, crossing the boundary tier-up overrides the
#' base rarity multiplier with a fixed jump (50/80/150%).
#'
#' @return list(crosses = logical, jump_pct = numeric, risk = c("low","medium","high"))
#' @export
boundary_jump <- function(current_ovr, delta_ovr, rarity) {
  out <- list(crosses = FALSE, jump_pct = 0, risk = "low")
  if (is.null(rarity) || is.na(rarity)) return(out)
  if (delta_ovr <= 0) return(out)
  new_ovr <- current_ovr + delta_ovr
  r <- tolower(rarity)
  if (grepl("gold", r) && current_ovr < 85 && new_ovr >= 85) {
    out$crosses <- TRUE; out$jump_pct <- 1.50; out$risk <- "high"
  } else if (grepl("silver", r) && current_ovr < 80 && new_ovr >= 80) {
    out$crosses <- TRUE; out$jump_pct <- 0.80; out$risk <- "high"
  } else if (grepl("bronze", r) && current_ovr < 75 && new_ovr >= 75) {
    out$crosses <- TRUE; out$jump_pct <- 0.50; out$risk <- "medium"
  }
  out
}

#' Confidence label from |z|.
#' @export
ovr_confidence <- function(z) {
  if (is.na(z)) return("low")
  az <- abs(z)
  if (az > 1.5) return("high")
  if (az > 0.8) return("medium")
  "low"
}

#' End-to-end OVR predictor.
#' @param stats_recent list (e.g. from get_recent_vs_season_stats()$recent)
#' @param stats_season same shape
#' @param role "hitter"/"pitcher"
#' @param current_ovr integer
#' @param rarity character
#' @return list with z, delta_ovr, base_pct, boundary, total_pct, confidence,
#'   components.
#' @export
predict_price_change <- function(stats_recent, stats_season, role,
                                 current_ovr, rarity) {
  zr <- ovr_z_score(stats_recent, stats_season, role = role)
  delta_ovr <- z_to_delta_ovr(zr$z)
  base_pct <- delta_ovr * rarity_pct_per_ovr(rarity)
  boundary <- boundary_jump(current_ovr, delta_ovr, rarity)
  total_pct <- if (boundary$crosses) max(base_pct, boundary$jump_pct) else base_pct
  list(
    z = zr$z,
    components = zr$components,
    delta_ovr = delta_ovr,
    base_pct = base_pct,
    boundary = boundary,
    total_pct = total_pct,
    confidence = ovr_confidence(zr$z)
  )
}

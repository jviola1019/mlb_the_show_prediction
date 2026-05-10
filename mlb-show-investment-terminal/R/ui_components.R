#' UI building blocks shared across tabs.
#'
#' All components are pure HTML factories — no Shiny inputs/outputs.
#' Tone tokens map to .pill-* classes defined in inst/www/theme.css.

#' Inline pill badge. Unknown tones fall back to "neutral".
#' @export
pill <- function(text, tone = "neutral") {
  valid <- c("neutral", "bull", "bear", "warn", "info",
             "diamond", "gold", "silver", "bronze")
  tone <- if (length(tone) == 1L && !is.na(tone) && tone %in% valid) tone
          else "neutral"
  htmltools::tags$span(
    class = paste0("pill pill-", tone),
    text
  )
}

#' Big-number stat block.
#' @export
stat <- function(label, value, sub = NULL, tone = "neutral") {
  htmltools::tags$div(
    class = paste("stat-box", paste0("stat-", tone)),
    htmltools::tags$div(class = "stat-label", toupper(label)),
    htmltools::tags$div(class = "stat-value", value),
    if (!is.null(sub)) htmltools::tags$div(class = "stat-sub", sub)
  )
}

#' Section header tag (e.g. "01 · FIND CARD").
#' @export
section_header <- function(num, title) {
  htmltools::tags$div(
    class = "section-header",
    htmltools::tags$span(class = "section-num", sprintf("%02d", as.integer(num))),
    htmltools::tags$span(class = "section-dot", "·"),
    htmltools::tags$span(class = "section-title", toupper(title))
  )
}

#' Recommendation signal pill (large, with neon glow).
#' @export
signal_pill <- function(action) {
  cls <- switch(action,
                "STRONG BUY"  = "signal-strong-buy",
                "BUY"         = "signal-buy",
                "STRONG SELL" = "signal-strong-sell",
                "SELL"        = "signal-sell",
                "HOLD"        = "signal-hold",
                "ABSTAIN"     = "signal-abstain",
                "signal-hold"
  )
  glyph <- if (action == "ABSTAIN") "⊘" else "◉"
  htmltools::tags$div(
    class = paste("signal-pill", cls),
    htmltools::tags$span(class = "signal-glyph", glyph),
    htmltools::tags$span(class = "signal-text", action),
    htmltools::tags$span(class = "signal-glyph", glyph)
  )
}

#' Per-tab "model + data version" banner.
#' Renders a thin line above each tab's first section telling the user
#' the model version, last code-update date, and a slot for the tab's
#' own freshness indicator.
#' @export
tab_version_banner <- function(tab_name,
                               model_version = "v1.1.0",
                               model_updated = "2026-05-04",
                               extra = NULL) {
  htmltools::tags$div(
    class = "tab-version-banner",
    htmltools::tags$span(class = "tvb-tab", toupper(tab_name)),
    htmltools::tags$span(class = "tvb-sep", "·"),
    htmltools::tags$span(class = "tvb-version",
                         paste("model", model_version)),
    htmltools::tags$span(class = "tvb-sep", "·"),
    htmltools::tags$span(class = "tvb-updated",
                         paste("updated", model_updated)),
    if (!is.null(extra)) htmltools::tagList(
      htmltools::tags$span(class = "tvb-sep", "·"), extra) else NULL
  )
}

#' Tier badge — DIAMOND / GOLD / SILVER / BRONZE / ABSTAIN.
#' @export
tier_pill <- function(tier) {
  cls <- switch(tier,
                "DIAMOND" = "tier-diamond",
                "GOLD"    = "tier-gold",
                "SILVER"  = "tier-silver",
                "BRONZE"  = "tier-bronze",
                "ABSTAIN" = "tier-abstain",
                "tier-abstain")
  glyph <- switch(tier,
                  "DIAMOND" = "♦", "GOLD" = "★",
                  "SILVER" = "◆", "BRONZE" = "▲",
                  "⊘")
  htmltools::tags$span(
    class = paste("pill tier-pill", cls),
    htmltools::tags$span(class = "tier-glyph", glyph),
    htmltools::tags$span(class = "tier-label", tier)
  )
}

#' Freshness badge for the CARD-tab listing fetch timestamp.
#' tone is decided by age in hours: <1 fresh, 1-24 amber, >=48 bad.
#' @export
freshness_badge <- function(fetched_at = NULL, label = "LISTING FETCHED") {
  if (is.null(fetched_at) || !inherits(fetched_at, c("POSIXct", "POSIXt"))) {
    return(htmltools::tags$span(class = "pill freshness-unknown",
                                paste(label, "—")))
  }
  age_h <- as.numeric(difftime(Sys.time(), fetched_at, units = "hours"))
  cls <- if (!is.finite(age_h)) "freshness-unknown" else
         if (age_h < 1)         "freshness-fresh"   else
         if (age_h < 24)        "freshness-stale"   else
                                "freshness-bad"
  htmltools::tags$span(
    class = paste("pill freshness", cls),
    sprintf("%s · %s", label, format(fetched_at, "%Y-%m-%d %H:%M %Z"))
  )
}

#' Static badge that explicitly disclaims LLM commentary as a non-signal.
#' @export
not_a_signal_badge <- function() {
  htmltools::tags$span(
    class = "not-a-signal-badge",
    "NOT A SIGNAL · COMMENTARY ONLY"
  )
}

#' Roster update banner — color coded by upcoming update type.
#' @param today Date.
#' @param updates data.frame from data/roster_updates.rds.
#' @export
roster_banner <- function(today = Sys.Date(), updates = NULL) {
  if (is.null(updates)) {
    p <- system.file("data", "roster_updates.rds", package = "mlbshowterminal")
    if (!nzchar(p)) {
      p <- file.path("data", "roster_updates.rds")
    }
    if (file.exists(p)) updates <- readRDS(p)
  }
  if (is.null(updates) || nrow(updates) == 0L) {
    return(htmltools::tags$div(class = "roster-banner roster-empty",
                               "ROSTER UPDATE  —  no schedule loaded"))
  }
  upcoming <- updates[updates$date >= today, , drop = FALSE]
  if (nrow(upcoming) == 0L) {
    return(htmltools::tags$div(class = "roster-banner roster-empty",
                               "ROSTER UPDATE  —  schedule complete"))
  }
  nxt <- upcoming[1L, ]
  days_until <- as.integer(nxt$date - today)
  is_attribute <- nxt$type == "attribute"
  is_imminent <- days_until <= 2L
  cls <- paste("roster-banner",
               if (is_attribute) "roster-attribute" else "roster-transaction")
  countdown_text <- if (days_until == 0L) "TODAY" else
    sprintf("IN %dD · %s", days_until, toupper(nxt$type))
  htmltools::tags$div(
    class = cls,
    htmltools::tags$div(class = "roster-label", "ROSTER UPDATE"),
    htmltools::tags$div(class = "roster-main", countdown_text),
    htmltools::tags$div(class = "roster-sub",
      sprintf("%s · %s", format(nxt$date, "%a %b %d"), nxt$notes)),
    if (is_attribute) pill("ATTR", "warn") else
      if (is_imminent) pill("SOON", "info") else NULL
  )
}

#' Flag list — converts the recommendation_score()$flags structure to inline pills.
#' @export
flag_list <- function(flags) {
  if (length(flags) == 0L) {
    return(htmltools::tags$div(class = "flag-list flag-list-empty",
                               "no flags"))
  }
  htmltools::tags$div(
    class = "flag-list",
    lapply(flags, function(f) pill(f$text, f$level))
  )
}

#' Holographic data-density indicator (5 emerald dots, opacity scaled to score in [0,1]).
#' @export
density_dots <- function(score = 0.5) {
  score <- max(0, min(1, as.numeric(score)))
  filled <- round(score * 5)
  htmltools::tags$div(
    class = "density-dots",
    title = sprintf("liquidity = %.0f%%", score * 100),
    lapply(seq_len(5), function(i) {
      htmltools::tags$span(
        class = if (i <= filled) "dot dot-on" else "dot dot-off"
      )
    })
  )
}

#' Map a rarity string to one of the four card-pill tones (or neutral).
#' @export
rarity_pill_tone <- function(rarity) {
  if (is.null(rarity) || is.na(rarity)) return("neutral")
  r <- tolower(as.character(rarity))
  if (grepl("diamond", r, fixed = TRUE)) return("diamond")
  if (grepl("gold",    r, fixed = TRUE)) return("gold")
  if (grepl("silver",  r, fixed = TRUE)) return("silver")
  if (grepl("bronze",  r, fixed = TRUE)) return("bronze")
  if (grepl("common",  r, fixed = TRUE)) return("neutral")
  "neutral"
}

#' Boot loading screen — appears until the first reactive output renders.
#' @export
loading_screen <- function() {
  htmltools::tags$div(
    id = "bootscreen",
    htmltools::tags$div(class = "boot-grid"),
    htmltools::tags$div(class = "boot-scanner"),
    htmltools::tags$div(
      class = "boot-content",
      htmltools::tags$div(class = "boot-title", "MLB · TERMINAL"),
      htmltools::tags$div(class = "boot-subtitle", "INVESTMENT QUANT · v1.0"),
      htmltools::tags$div(class = "boot-bar", htmltools::tags$div(class = "boot-bar-fill"))
    )
  )
}

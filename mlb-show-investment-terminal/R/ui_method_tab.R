#' METHOD tab - static reference for the current engines.
#' @export
ui_method_tab <- function() {
  bslib::nav_panel(
    title = "METHOD",
    icon = bsicons::bs_icon("book"),
    htmltools::tags$div(
      class = "tab-panel method-tab",

      tab_version_banner("METHOD",
        extra = htmltools::tags$span("engine contracts + validation reference")),
      section_header(1, "ARCHITECTURE"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ul(
          htmltools::tags$li("Hybrid architecture: Shiny/R is the UI shell; ",
                             "Python owns flip math, upgrade thresholds, ",
                             "formula validation, and historical backtests."),
          htmltools::tags$li("If Python is unavailable on a host, R fallback ",
                             "engines keep the tabs functional and mark the ",
                             "backend reason codes accordingly."),
          htmltools::tags$li("Live data only: mlb26.theshow.com listing.json plus ",
                             "statsapi.mlb.com. No synthetic prices or player data."),
          htmltools::tags$li("Memoised in-memory cache: 10 min The Show, ",
                             "1 hr MLB Stats. Python exchanges use temp JSON ",
                             "files that are deleted after each call.")
        )
      ),

      section_header(2, "ENGINES"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ol(
          htmltools::tags$li("Flip engine: raw ask/bid, after_tax_sale = ask * 0.90, ",
                             "profit = after_tax_sale - bid, ROI = profit / bid."),
          htmltools::tags$li("Upgrade engine: current OVR, rarity, new_rank when ",
                             "available, recent-vs-season stats, and distance to ",
                             "the next rarity threshold."),
          htmltools::tags$li("Forecast engine: price history, log returns, stationary ",
                             "block bootstrap, walk-forward CV, and calibration diagnostics."),
          htmltools::tags$li("Forecast EV is non-executable. It is shown separately ",
                             "from flip ROI and cannot overwrite flip formula math.")
        )
      ),

      section_header(3, "RECOMMENDATION RUBRIC"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$pre(class = "rubric",
"flip:
  BUY      : bid/ask present, after-tax profit > 0, ROI floor passes,
             and liquidity proxy is available
  HOLD     : executable book, but ROI edge does not clear the floor
  SELL     : executable book with materially negative after-tax ROI
  NO TRADE : missing/zero bid or ask, unavailable spread, or no liquidity

upgrade:
  BUY SPECULATIVE : near-threshold high-confidence candidate, or real
                    new_rank crosses the next rarity threshold
  WATCH           : upgrade probability exists but conservative buy gate fails
  HOLD            : no clear upgrade or downgrade edge
  AVOID           : stats/new_rank unavailable
  SELL            : downgrade probability dominates

forecast:
  FORECAST BULLISH / FLAT / BEARISH is diagnostic only. It is not
  executable flip EV and does not create a flip BUY/SELL.")
      ),

      section_header(4, "VALIDATION"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ul(
          htmltools::tags$li("Validate tab compares manual flip math against ",
                             "the engine formula and flags tolerance mismatches."),
          htmltools::tags$li("Backtest helpers evaluate real historical roster ",
                             "labels when supplied through Python CSV/JSON inputs: ",
                             "Brier, precision, recall, and calibration curve."),
          htmltools::tags$li("If data is missing, outputs are marked unavailable ",
                             "instead of guessed.")
        )
      )
    )
  )
}

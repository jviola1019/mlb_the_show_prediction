#' METHOD tab — pure markdown documenting the quant pipeline.
#' @export
ui_method_tab <- function() {
  bslib::nav_panel(
    title = "METHOD",
    icon = bsicons::bs_icon("book"),
    htmltools::tags$div(
      class = "tab-panel method-tab",

      section_header(1, "ARCHITECTURE"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ul(
          htmltools::tags$li("Server-side R via Shiny — no browser CORS."),
          htmltools::tags$li("Live data only: mlb26.theshow.com listing.json + ",
                             "statsapi.mlb.com — no synthetic prices."),
          htmltools::tags$li("Memoised in-memory cache (10 min TTL on The Show, ",
                             "1 hr on MLB Stats)."),
          htmltools::tags$li("Optional claude-opus-4-7 cross-check via env-gated ",
                             "ANTHROPIC_API_KEY (prompt caching enabled).")
        )
      ),

      section_header(2, "QUANT PIPELINE"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ol(
          htmltools::tags$li("Pull price_history from listing.json (~168 hourly samples)."),
          htmltools::tags$li("log-returns r_t = ln(p_t / p_{t-1}); drop NA/zero/negative."),
          htmltools::tags$li("Block length L via Politis-White b.star (np::b.star) ",
                             "with floor(N^0.4) fallback."),
          htmltools::tags$li("Stationary block bootstrap (Politis-Romano 1994) — ",
                             "1500 sims main, 1000 per horizon."),
          htmltools::tags$li("OLS log-price slope with Newey-West HAC SE ",
                             "(sandwich::NeweyWest, lag = floor(4*(N/100)^(2/9)))."),
          htmltools::tags$li("Hurst exponent (R/S analysis) for regime ID."),
          htmltools::tags$li("EV with 10% sell-tax and bid/ask spread; ½-Kelly sizing."),
          htmltools::tags$li("Walk-forward CV: per-trade Brier + IC, bootstrap CIs ",
                             "via boot::tsboot (block) or boot::boot (per-trade)."),
          htmltools::tags$li("Isotonic recalibration (probably::cal_estimate_isotonic, ",
                             "cross-checked against custom PAVA at 1e-6).")
        )
      ),

      section_header(3, "RECOMMENDATION RUBRIC"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$pre(class = "rubric",
"score additions:
  +EV>5%   : +2  (bull)
  +EV>1%   : +1  (bull)
  -EV<-5%  : -2  (bear)
  -EV<-1%  : -1  (bear)
  drift sig+ (HAC p<0.05, slope>0): +1
  drift sig- (HAC p<0.05, slope<0): -1
  z30 < -1.5: +1 (oversold)
  z30 > +1.5: -1 (overbought)

flags (no score, info/warn only):
  spread > 15%               : warn
  CV IC upper-CI < 0         : warn  CV IC<0 (sig)
  CV IC point  < -0.10       : warn  CV IC<0
  Hurst > 0.6                : info  trending
  Hurst < 0.4                : info  mean-revert

action map:
  score >= +3 -> STRONG BUY
  score >= +1 -> BUY
  score == 0  -> HOLD
  score <= -1 -> SELL
  score <= -3 -> STRONG SELL")
      ),

      section_header(4, "LIMITATIONS"),
      htmltools::tags$div(class = "panel",
        htmltools::tags$ul(
          htmltools::tags$li("Price histories are short (~168 points). Variance ",
                             "of estimators is high. The CIs are honest, not narrow."),
          htmltools::tags$li("The block bootstrap preserves short-range autocorrelation, ",
                             "not regime breaks. A roster attribute update IS a regime break."),
          htmltools::tags$li("Walk-forward CV requires ≥ 6×horizon samples; some ",
                             "thinly-traded cards will return NULL."),
          htmltools::tags$li("OVR predictor uses only 14d vs season splits. Real ",
                             "SDS roster decisions are not fully observable.")
        )
      )
    )
  )
}

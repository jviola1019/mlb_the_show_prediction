#' Market microstructure / flip economics.
#'
#' This module is intentionally independent from the time-series forecast.
#' A flip is executable only when both sides of the current book are present.
#' The marketplace tax is applied once, on sale proceeds.

.as_price <- function(x) {
  if (is.null(x) || length(x) == 0L) return(NA_real_)
  suppressWarnings(as.numeric(x[[1L]]))
}

.join_reason_codes <- function(x) {
  x <- unique(as.character(x))
  x <- x[nchar(x) > 0L]
  paste(x, collapse = ",")
}

.coerce_liquidity <- function(liquidity) {
  if (is.null(liquidity)) {
    return(list(score = NA_real_, n = 0L, recent = NA_integer_))
  }
  if (is.list(liquidity) && all(c("score", "n", "recent") %in% names(liquidity))) {
    return(list(
      score = as.numeric(liquidity$score %||% NA_real_),
      n = as.integer(liquidity$n %||% 0L),
      recent = as.integer(liquidity$recent %||% NA_integer_)
    ))
  }
  if (is.list(liquidity)) return(liquidity_score(liquidity))
  list(score = NA_real_, n = 0L, recent = NA_integer_)
}

#' Compute executable flip math from raw book prices.
#'
#' @param sell_price numeric. Current best sell / ask price.
#' @param buy_price numeric. Current best buy / bid price.
#' @param liquidity NULL, a liquidity_score() list, or completed_orders.
#' @param tax_rate numeric. Marketplace sell-side tax.
#' @param min_roi numeric. Conservative BUY floor.
#' @param min_liquidity_score numeric. Minimum available liquidity proxy.
#' @return list with raw inputs, formula outputs, executable flag, action,
#'   reason codes, and failed gates.
#' @export
flip_economics <- function(sell_price, buy_price, liquidity = NULL,
                           tax_rate = 0.10,
                           min_roi = 0.01,
                           min_liquidity_score = 0.05) {
  ask <- .as_price(sell_price)
  bid <- .as_price(buy_price)
  liq <- .coerce_liquidity(liquidity)

  reasons <- character(0)
  failed <- character(0)

  if (!is.finite(ask) || ask <= 0) {
    reasons <- c(reasons, "MISSING_SELL_PRICE")
    failed <- c(failed, "sell_price")
  }
  if (!is.finite(bid) || bid <= 0) {
    reasons <- c(reasons, "MISSING_BUY_PRICE")
    failed <- c(failed, "buy_price")
  }

  executable_prices <- is.finite(ask) && ask > 0 && is.finite(bid) && bid > 0
  after_tax_sale <- if (is.finite(ask) && ask > 0) ask * (1 - tax_rate) else NA_real_
  profit <- if (executable_prices) after_tax_sale - bid else NA_real_
  roi <- if (executable_prices) profit / bid else NA_real_
  spread_pct <- if (executable_prices) (ask - bid) / ask else NA_real_

  if (!executable_prices) {
    reasons <- c(reasons, "NON_EXECUTABLE_BOOK")
  }
  if (!is.finite(spread_pct)) {
    reasons <- c(reasons, "SPREAD_UNAVAILABLE")
    failed <- c(failed, "spread")
  }

  liquidity_available <- is.finite(liq$score) && liq$score >= min_liquidity_score
  if (!is.finite(liq$score)) {
    reasons <- c(reasons, "LIQUIDITY_UNAVAILABLE")
    failed <- c(failed, "liquidity")
  } else if (liq$score < min_liquidity_score) {
    reasons <- c(reasons, "LIQUIDITY_BELOW_FLOOR")
    failed <- c(failed, "liquidity")
  }

  if (is.finite(profit) && profit > 0) {
    reasons <- c(reasons, "POSITIVE_AFTER_TAX_EDGE")
  } else if (is.finite(profit) && profit < 0) {
    reasons <- c(reasons, "NEGATIVE_AFTER_TAX_EDGE")
  } else if (is.finite(profit)) {
    reasons <- c(reasons, "BREAKEVEN_AFTER_TAX")
  }

  if (is.finite(roi) && roi < min_roi) {
    reasons <- c(reasons, "ROI_BELOW_FLOOR")
    failed <- c(failed, "roi")
  }

  executable <- executable_prices && is.finite(spread_pct) && liquidity_available
  action <- "NO TRADE"
  if (executable) {
    if (is.finite(roi) && roi >= min_roi && is.finite(profit) && profit > 0) {
      action <- "BUY"
    } else if (is.finite(roi) && roi <= -0.05) {
      action <- "SELL"
    } else {
      action <- "HOLD"
    }
  }

  list(
    sell_price = ask,
    buy_price = bid,
    after_tax_sale = after_tax_sale,
    profit = profit,
    roi = roi,
    spread_pct = spread_pct,
    liquidity_score = liq$score,
    liquidity_n = liq$n,
    liquidity_recent = liq$recent,
    executable = executable,
    action = action,
    reason_codes = unique(reasons),
    reason_codes_csv = .join_reason_codes(reasons),
    failed_gates = unique(failed),
    failed_gates_csv = .join_reason_codes(failed),
    formula = sprintf(
      "after_tax_sale = %.4f * %.2f; profit = after_tax_sale - %.4f; roi = profit / %.4f",
      ask, 1 - tax_rate, bid, bid
    )
  )
}

#' Compare manual flip math against the engine output.
#' @export
validate_flip_formula <- function(sell_price, buy_price, engine = NULL,
                                  tolerance = 1e-6,
                                  tax_rate = 0.10) {
  if (is.null(engine)) {
    engine <- flip_economics(sell_price, buy_price,
                             liquidity = list(score = 1, n = 1L, recent = 1L),
                             tax_rate = tax_rate,
                             min_liquidity_score = 0)
  }
  ask <- .as_price(sell_price)
  bid <- .as_price(buy_price)
  manual_after_tax <- if (is.finite(ask) && ask > 0) ask * (1 - tax_rate) else NA_real_
  manual_profit <- if (is.finite(bid) && bid > 0 && is.finite(manual_after_tax)) {
    manual_after_tax - bid
  } else NA_real_
  manual_roi <- if (is.finite(bid) && bid > 0 && is.finite(manual_profit)) {
    manual_profit / bid
  } else NA_real_
  diffs <- c(
    after_tax_sale = abs((engine$after_tax_sale %||% NA_real_) - manual_after_tax),
    profit = abs((engine$profit %||% NA_real_) - manual_profit),
    roi = abs((engine$roi %||% NA_real_) - manual_roi)
  )
  mismatch <- any(is.finite(diffs) & diffs > tolerance)
  list(
    manual_after_tax_sale = manual_after_tax,
    manual_profit = manual_profit,
    manual_roi = manual_roi,
    model_after_tax_sale = engine$after_tax_sale %||% NA_real_,
    model_profit = engine$profit %||% NA_real_,
    model_roi = engine$roi %||% NA_real_,
    max_abs_diff = if (all(is.na(diffs))) NA_real_ else max(diffs, na.rm = TRUE),
    tolerance = tolerance,
    mismatch = mismatch
  )
}

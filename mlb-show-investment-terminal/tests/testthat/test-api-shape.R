# API shape tests via mocked httr2::req_perform.
# Network is never actually contacted in these tests.

mock_resp <- function(status = 200L, body = list(), url = "http://mock") {
  json <- as.character(jsonlite::toJSON(body, auto_unbox = TRUE,
                                        null = "null"))
  httr2::response(
    status_code = status,
    headers = "content-type: application/json",
    body = charToRaw(json),
    url = url
  )
}

with_mocked_perform <- function(handler, code) {
  testthat::with_mocked_bindings(
    req_perform = handler,
    code = code,
    .package = "httr2"
  )
}

test_that("search_card_uncached parses listings.json fixture", {
  fixture <- jsonlite::fromJSON(
    test_path("fixtures", "listings_trout.json"),
    simplifyVector = FALSE
  )
  with_mocked_perform(function(req, ...) mock_resp(200L, fixture), {
    theshow_clear_cache()
    res <- search_card_uncached("Mike Trout")
    expect_gt(length(res$listings), 0)
    uuid <- res$listings[[1]]$item$uuid
    expect_true(is_valid_uuid(uuid))
    expect_equal(res$listings[[1]]$item$rarity, "Diamond")
  })
})

test_that("get_listing_uncached rejects bad uuid before network", {
  res <- get_listing_uncached("not-a-uuid")
  expect_equal(res$error, "invalid uuid")
  expect_null(res$item)
})

test_that("extract_price_history yields a tidy frame", {
  fixture <- jsonlite::fromJSON(
    test_path("fixtures", "listing_trout.json"),
    simplifyVector = FALSE
  )
  ph <- extract_price_history(fixture)
  expect_s3_class(ph, "data.frame")
  expect_equal(nrow(ph), 5L)
  expect_true(all(ph$price > 0))
  expect_true(all(diff(as.numeric(ph$timestamp)) >= 0))
})

test_that("Year fallback skips empty years", {
  call_count <- 0L
  handler <- function(req, ...) {
    call_count <<- call_count + 1L
    url <- req$url %||% ""
    if (grepl("mlb26", url)) {
      mock_resp(200L, list(listings = list()), url = url)
    } else if (grepl("mlb25", url)) {
      mock_resp(200L, list(
        listings = list(list(
          listing_name = "X",
          item = list(uuid = "abcdef0123456789abcdef0123456789",
                      rarity = "Gold")
        ))
      ), url = url)
    } else {
      mock_resp(404L, list(), url = url)
    }
  }
  with_mocked_perform(handler, {
    theshow_clear_cache()
    res <- search_card_uncached("X")
    expect_equal(res$year, 25L)
    expect_gt(length(res$listings), 0L)
    expect_gte(call_count, 2L)
  })
})

test_that("mlb_search_player_uncached parses people fixture", {
  fixture <- jsonlite::fromJSON(
    test_path("fixtures", "mlb_search_trout.json"),
    simplifyVector = FALSE
  )
  with_mocked_perform(function(req, ...) mock_resp(200L, fixture), {
    mlb_clear_cache()
    p <- mlb_search_player_uncached("Mike Trout")
    expect_equal(p$id, 545361L)
    expect_equal(p$full_name, "Mike Trout")
    expect_match(p$primary_position, "Outfielder")
  })
})

test_that("mlb_player_stats_uncached coerces stat strings to numeric", {
  fake <- list(
    stats = list(list(splits = list(list(stat = list(
      ops = "0.987", avg = "0.305", obp = "0.412", slg = "0.575"
    )))))
  )
  with_mocked_perform(function(req, ...) mock_resp(200L, fake), {
    mlb_clear_cache()
    s <- mlb_player_stats_uncached(545361L, "2026-04-18", "2026-05-02",
                                   group = "hitting")
    expect_type(s$ops, "double")
    expect_equal(s$ops, 0.987)
  })
})

test_that("anthropic_available returns FALSE without env var", {
  withr::with_envvar(c(ANTHROPIC_API_KEY = ""), {
    expect_false(anthropic_available())
    expect_null(anthropic_card_summary(list(name = "x"), list(),
                                       list(action = "HOLD",
                                            score = 0L, flags = list())))
  })
})

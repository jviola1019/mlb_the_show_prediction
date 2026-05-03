# Deploy to shinyapps.io.
# Reads SHINYAPPS_NAME / SHINYAPPS_TOKEN / SHINYAPPS_SECRET from env.
# Run from repo root: Rscript deploy.R
deploy_to_shinyapps <- function(app_name = "mlb-show-terminal") {
  needed <- c("SHINYAPPS_NAME", "SHINYAPPS_TOKEN", "SHINYAPPS_SECRET")
  missing <- needed[Sys.getenv(needed) == ""]
  if (length(missing) > 0L) {
    stop("Missing env vars: ", paste(missing, collapse = ", "),
         ". See .Renviron.template.")
  }
  rsconnect::setAccountInfo(
    name   = Sys.getenv("SHINYAPPS_NAME"),
    token  = Sys.getenv("SHINYAPPS_TOKEN"),
    secret = Sys.getenv("SHINYAPPS_SECRET")
  )
  rsconnect::deployApp(
    appDir = ".",
    appName = app_name,
    appFiles = c(
      "app.R", "DESCRIPTION", "NAMESPACE",
      list.files("R", full.names = TRUE),
      list.files("data", full.names = TRUE),
      list.files("www", full.names = TRUE, recursive = TRUE)
    ),
    forceUpdate = TRUE,
    launch.browser = FALSE
  )
}

if (!interactive()) deploy_to_shinyapps()

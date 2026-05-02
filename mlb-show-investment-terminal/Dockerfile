FROM rocker/shiny:4.4

# System libs needed by sandwich, np, plotly, reactable, httr2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev libssl-dev libxml2-dev \
    libfontconfig1-dev libfreetype6-dev libpng-dev libtiff-dev libjpeg-dev \
    libharfbuzz-dev libfribidi-dev libcairo2-dev \
 && rm -rf /var/lib/apt/lists/*

# Use renv to lock dependencies for reproducibility
WORKDIR /srv/shiny-server/app
RUN R -e "install.packages('renv', repos='https://cloud.r-project.org')"

COPY .Rprofile .Rprofile
COPY renv.lock renv.lock
COPY renv/activate.R renv/activate.R
RUN R -e "renv::restore(prompt = FALSE)"

# App source last so dependency restore is cached.
COPY . .

EXPOSE 3838
CMD ["R", "-e", "shiny::runApp('/srv/shiny-server/app', host='0.0.0.0', port=3838, launch.browser=FALSE)"]

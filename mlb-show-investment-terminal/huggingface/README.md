---
title: MLB Show Investment Terminal
emoji: ⚾
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
---

# MLB Show Investment Terminal

Docker Space deployment for the React + Python rebuild.

This Space runs one Docker container: Vite builds the React terminal, FastAPI serves `/api` and the static app, and Python owns all quant decisions. Runtime secrets and variables belong in Hugging Face Space Settings; do not place secrets in frontend code.

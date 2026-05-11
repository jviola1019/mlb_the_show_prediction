FROM node:25-slim AS frontend

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MLB_SHOW_STATIC_DIR=/app/frontend/dist \
    PORT=7860

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user:user pyproject.toml requirements-api.txt ./
COPY --chown=user:user python/ ./python/
RUN pip install --no-cache-dir -e .

COPY --chown=user:user --from=frontend /build/frontend/dist ./frontend/dist

USER user
EXPOSE 7860
CMD ["sh", "-c", "uvicorn mlb_show_terminal.api:app --host 0.0.0.0 --port ${PORT:-7860}"]

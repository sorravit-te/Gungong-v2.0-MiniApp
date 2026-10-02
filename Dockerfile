FROM node:22.12.0-bookworm-slim AS frontend-build

WORKDIR /build/src/frontend

COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci

COPY src/frontend/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-compile -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && python -c "from pathlib import Path; [p.unlink() for p in Path('/usr/local/lib/python3.12').rglob('*.pyc')]" \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /ms-playwright

COPY src/backend ./src/backend
COPY --from=frontend-build /build/src/frontend/dist ./src/backend/static

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app/logs

USER appuser

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn src.backend.main:app --host 0.0.0.0 --port \"${PORT:-10000}\""]

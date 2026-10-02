# Local prototype, deliberately independent of the API/Firestore/AI image.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright URL_RENDER_ENABLED=true HOME=/tmp
WORKDIR /app
COPY deploy/local-url-renderer/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && useradd --uid 10001 --no-create-home renderer
# Whitelist only the worker and reusable public-network/browser boundary.
COPY src/backend/__init__.py ./src/backend/__init__.py
COPY src/backend/core/__init__.py src/backend/core/config.py src/backend/core/performance_config.py ./src/backend/core/
COPY src/backend/services/__init__.py src/backend/services/url_safety_service.py \
    src/backend/services/url_renderer_service.py src/backend/services/renderer_worker_app.py ./src/backend/services/
USER 10001:10001
EXPOSE 8071
CMD ["python", "-m", "src.backend.services.renderer_worker_app"]

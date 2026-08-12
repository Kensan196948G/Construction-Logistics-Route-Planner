# Construction Logistics Route Planner — runtime image
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies + the app package from pyproject (single source of truth).
# The source tree is kept on disk because the app serves static files via the
# relative path "app/static" (resolved against WORKDIR at runtime).
COPY pyproject.toml ./
COPY app ./app
RUN pip install '.[pg]'

# Drop privileges: uvicorn binds 8000 (>1024), so root is unnecessary.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

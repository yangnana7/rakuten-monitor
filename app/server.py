"""FastAPI server for Rakuten Monitor metrics export."""

import os
import time
from fastapi import FastAPI, Response, status
from prometheus_client import (
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# ──────────────────────────────────────────────
# PROMETHEUS METRICS - Import from metrics.py definitions
from metrics import (
    system_info,
)

# Additional FastAPI-specific metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests handled by FastAPI",
    ["method", "endpoint", "status"],
)

app_uptime_seconds = Gauge("app_uptime_seconds", "Application uptime in seconds")

# Set startup time for uptime calculation
startup_time = time.time()

# ──────────────────────────────────────────────
# FASTAPI
app = FastAPI(title="Rakuten Monitor API", version="0.1.0")


@app.on_event("startup")
def _startup_populate():
    """Startup handler to populate initial metrics."""
    # Initialize system info
    system_info.info(
        {
            "version": "3.0.0",
            "component": "rakuten_monitor",
            "environment": os.getenv("ENVIRONMENT", "production"),
        }
    )


@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Middleware to track HTTP requests."""
    response = await call_next(request)

    # Record HTTP request metrics
    http_requests_total.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    # Update uptime
    app_uptime_seconds.set(time.time() - startup_time)

    return response


@app.get("/healthz", status_code=status.HTTP_200_OK)
def healthz() -> dict[str, str]:
    """コンテナ用ヘルスチェック."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus 互換エンドポイント."""
    # Update uptime before generating metrics
    app_uptime_seconds.set(time.time() - startup_time)

    # Generate metrics from the default registry (includes all imported metrics)
    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

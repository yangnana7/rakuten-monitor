"""FastAPI server for Rakuten Monitor metrics export."""

from fastapi import FastAPI, Response, status
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ──────────────────────────────────────────────
# PROMETHEUS METRICS
registry = CollectorRegistry(auto_describe=True)

REQ_COUNTER = Counter(
    "rakuten_requests_total", "Total HTTP requests handled", registry=registry
)
ITEM_GAUGE = Gauge(
    "rakuten_available_items",
    "Current number of tracked items available",
    registry=registry,
)
# 初期値 0
ITEM_GAUGE.set(0)

# ──────────────────────────────────────────────
# FASTAPI
app = FastAPI(title="Rakuten Monitor API", version="0.1.0")


@app.on_event("startup")
def _startup_populate():
    """Startup handler to populate initial metrics."""
    # TODO: item count を DB から取得し ITEM_GAUGE.set(n)
    pass


@app.get("/healthz", status_code=status.HTTP_200_OK)
def healthz() -> dict[str, str]:
    """コンテナ用ヘルスチェック."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus 互換エンドポイント."""
    REQ_COUNTER.inc()
    payload = generate_latest(registry)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

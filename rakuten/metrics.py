"""
Prometheus メトリクス定義 - rakuten module
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import logging
import time

logger = logging.getLogger(__name__)

# メトリクス定義
items_fetched_total = Counter(
    "rakuten_items_fetched_total", "Total number of items fetched from Rakuten"
)

changes_detected_total = Counter(
    "rakuten_changes_detected_total",
    "Total number of changes detected",
    ["change_type"],
)

run_duration_seconds = Histogram(
    "rakuten_run_duration_seconds", "Duration of monitoring run in seconds"
)

fetch_duration_seconds = Histogram(
    "rakuten_fetch_duration_seconds", "Duration of page fetch in seconds", ["method"]
)

last_run_status = Gauge(
    "rakuten_last_run_status", "Status of last monitoring run (1=success, 0=failure)"
)

last_run_timestamp = Gauge(
    "rakuten_last_run_timestamp", "Timestamp of last monitoring run"
)

discord_notifications_total = Counter(
    "rakuten_discord_notifications_total",
    "Total Discord notifications sent",
    ["notification_type", "status"],
)


def start_metrics_server(port: int = 8000):
    """Prometheusメトリクスサーバーを開始"""
    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        raise


def record_items_fetched(count: int):
    """取得した商品数を記録"""
    items_fetched_total.inc(count)


def record_change_detected(change_type: str):
    """検出した変更を記録"""
    changes_detected_total.labels(change_type=change_type).inc()


def record_run_success():
    """実行成功を記録"""
    last_run_status.set(1)
    last_run_timestamp.set(time.time())


def record_run_failure():
    """実行失敗を記録"""
    last_run_status.set(0)
    last_run_timestamp.set(time.time())


def record_discord_notification(notification_type: str, success: bool):
    """Discord通知を記録"""
    status = "success" if success else "failure"
    discord_notifications_total.labels(
        notification_type=notification_type, status=status
    ).inc()


def record_fetch_attempt(method: str, success: bool, duration: float = None):
    """フェッチ試行を記録"""
    if duration is not None:
        fetch_duration_seconds.labels(method=method).observe(duration)

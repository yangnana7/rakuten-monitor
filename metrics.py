#!/usr/bin/env python3
"""
Prometheus メトリクス定義
"""

import os
import logging
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server

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

fetch_attempts_total = Counter(
    "rakuten_fetch_attempts_total",
    "Total fetch attempts by method",
    ["method", "status"],
)

last_run_status = Gauge(
    "rakuten_last_run_status", "Status of last monitoring run (1=success, 0=failure)"
)

last_run_timestamp = Gauge("rakuten_last_run_timestamp", "Timestamp of last monitoring run")

discord_notifications_total = Counter(
    "rakuten_discord_notifications_total",
    "Total Discord notifications sent",
    ["notification_type", "status"],
)

database_operations_total = Counter(
    "rakuten_database_operations_total",
    "Total database operations",
    ["operation_type", "status"],
)

upsert_duration_seconds = Histogram(
    "rakuten_upsert_duration_seconds",
    "Duration of bulk upsert operations in seconds",
    ["database_type"],
)

upsert_items_total = Counter(
    "rakuten_upsert_items_total",
    "Total items processed in upsert operations",
    ["database_type"],
)

system_info = Info("rakuten_system_info", "System information")


class MetricsServer:
    def __init__(self, port: int = None):
        self.port = port or int(os.getenv("METRICS_PORT", "9100"))
        self.server_started = False

    def start_server(self):
        """Prometheusメトリクスサーバーを開始"""
        if self.server_started:
            logger.warning("Metrics server already started")
            return

        try:
            start_http_server(self.port)
            self.server_started = True
            logger.info(f"Prometheus metrics server started on port {self.port}")

            # システム情報を設定
            system_info.info(
                {
                    "version": "3.0.0",
                    "component": "rakuten_monitor",
                    "environment": os.getenv("ENVIRONMENT", "production"),
                }
            )

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
    import time

    last_run_timestamp.set(time.time())


def record_run_failure():
    """実行失敗を記録"""
    last_run_status.set(0)
    import time

    last_run_timestamp.set(time.time())


def record_discord_notification(notification_type: str, success: bool):
    """Discord通知を記録"""
    status = "success" if success else "failure"
    discord_notifications_total.labels(notification_type=notification_type, status=status).inc()


def record_database_operation(operation_type: str, success: bool):
    """データベース操作を記録"""
    status = "success" if success else "failure"
    database_operations_total.labels(operation_type=operation_type, status=status).inc()


def record_fetch_attempt(method: str, success: bool, duration: float = None):
    """フェッチ試行を記録"""
    status = "success" if success else "failure"
    fetch_attempts_total.labels(method=method, status=status).inc()

    if duration is not None:
        fetch_duration_seconds.labels(method=method).observe(duration)


def record_upsert_operation(database_type: str, items_count: int, duration: float):
    """Upsert操作を記録"""
    upsert_duration_seconds.labels(database_type=database_type).observe(duration)
    upsert_items_total.labels(database_type=database_type).inc(items_count)


# グローバルメトリクスサーバーインスタンス
metrics_server = MetricsServer()


def main():
    """メトリクスサーバーのテスト実行"""
    print(f"Starting Prometheus metrics server on port {metrics_server.port}")
    metrics_server.start_server()

    # テストメトリクス
    record_items_fetched(39)
    record_change_detected("NEW")
    record_run_success()
    record_discord_notification("change", True)
    record_database_operation("upsert", True)

    print(f"Metrics server running. Visit http://localhost:{metrics_server.port}/metrics")

    try:
        import time

        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Metrics server stopped")


if __name__ == "__main__":
    main()

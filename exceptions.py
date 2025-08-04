"""楽天商品監視ツール用カスタム例外"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _increment_exception_counter(exception_type: str, details: str = ""):
    """例外発生時のPrometheusカウンターを増加（オプション機能）"""
    try:
        # 循環インポートを回避するため、関数内でインポート
        from prometheus_client import get_prometheus_client
        
        client = get_prometheus_client()
        labels = {
            "exception_type": exception_type,
            "instance": os.getenv('HOSTNAME', 'localhost')
        }
        
        if details:
            # 詳細情報のハッシュを追加（プライバシー保護）
            labels["detail_hash"] = str(hash(details))[:8]
        
        client.increment_counter(
            name="monitor_exceptions_total",
            labels=labels,
            help_text="Total number of exceptions raised by type"
        )
        logger.debug(f"Exception counter incremented: {exception_type}")
        
    except Exception as e:
        # メトリクス送信の失敗は元の例外処理を阻害しない
        logger.debug(f"Failed to increment exception counter: {e}")


class RakutenMonitorError(Exception):
    """楽天監視ツールの基底例外クラス"""
    
    def __init__(self, message: str = ""):
        super().__init__(message)
        _increment_exception_counter("base_error", message)


class LayoutChangeError(RakutenMonitorError):
    """ページのHTML構造が変更された際に発生する例外"""
    
    def __init__(self, message: str = "", url: str = ""):
        super().__init__(message)
        self.url = url
        details = f"{message} {url}".strip()
        _increment_exception_counter("layout_change", details)


class DatabaseConnectionError(RakutenMonitorError):
    """データベース接続エラー"""
    
    def __init__(self, message: str = "", operation: str = ""):
        super().__init__(message)
        self.operation = operation
        details = f"{message} {operation}".strip()
        _increment_exception_counter("database_error", details)


class ConfigurationError(RakutenMonitorError):
    """設定ファイルの読み込みエラー"""
    
    def __init__(self, message: str = "", config_path: str = ""):
        super().__init__(message)
        self.config_path = config_path
        details = f"{message} {config_path}".strip()
        _increment_exception_counter("config_error", details)


class DiscordNotificationError(RakutenMonitorError):
    """Discord通知送信エラー"""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        
        # メトリクス用の詳細情報
        details = f"{message} HTTP:{status_code}" if status_code else message
        _increment_exception_counter("discord_error", details)
    
    def __str__(self):
        base_msg = super().__str__()
        if self.status_code:
            return f"{base_msg} (HTTP {self.status_code})"
        return base_msg


class PrometheusError(RakutenMonitorError):
    """Prometheus メトリクス送信エラー"""
    
    def __init__(self, message: str, metric_name: str = None):
        super().__init__(message)
        self.metric_name = metric_name
        
        # メトリクス用の詳細情報
        details = f"{message} metric:{metric_name}" if metric_name else message
        _increment_exception_counter("prometheus_error", details)


class NetworkError(RakutenMonitorError):
    """ネットワーク接続エラー"""
    
    def __init__(self, message: str, url: str = None, timeout: bool = False):
        super().__init__(message)
        self.url = url
        self.timeout = timeout
        
        # メトリクス用の詳細情報
        details_parts = [message]
        if url:
            details_parts.append(f"url:{url}")
        if timeout:
            details_parts.append("timeout:true")
        details = " ".join(details_parts)
        _increment_exception_counter("network_error", details)
"""Prometheus メトリクス送信クライアント"""

import os
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from .exceptions import PrometheusError
except ImportError:
    from exceptions import PrometheusError


logger = logging.getLogger(__name__)


class PrometheusClient:
    """Prometheus Pushgateway への メトリクス送信クライアント"""
    
    def __init__(self, pushgateway_url: Optional[str] = None, job_name: str = "rakuten_monitor"):
        self.pushgateway_url = pushgateway_url or os.getenv('PROM_PUSHGATEWAY_URL')
        self.job_name = job_name
        self.enabled = bool(self.pushgateway_url)
        
        if not self.enabled:
            logger.info("Prometheus Pushgateway URL not configured, metrics disabled")
        else:
            logger.info(f"Prometheus client initialized: {self.pushgateway_url}")
    
    def push_metric(self, name: str, labels: Dict[str, str], value: float = 1.0, 
                   metric_type: str = "counter", help_text: str = "") -> bool:
        """メトリクスを Pushgateway に送信"""
        if not self.enabled:
            logger.debug(f"Metrics disabled, skipping: {name}")
            return True
        
        try:
            # Prometheus exposition format でメトリクスデータを構築
            metric_data = self._build_metric_data(name, labels, value, metric_type, help_text)
            
            # Pushgateway URL を構築
            url = f"{self.pushgateway_url.rstrip('/')}/metrics/job/{self.job_name}"
            if labels:
                # instance ラベルがある場合は URL に追加
                if 'instance' in labels:
                    url += f"/instance/{labels['instance']}"
            
            # HTTP POST でメトリクス送信
            response = requests.post(
                url,
                data=metric_data,
                headers={'Content-Type': 'text/plain; charset=utf-8'},
                timeout=10
            )
            
            response.raise_for_status()
            logger.debug(f"Metric pushed successfully: {name}={value}")
            return True
            
        except requests.RequestException as e:
            error_msg = f"Failed to push metric {name}: {e}"
            logger.error(error_msg)
            raise PrometheusError(error_msg, metric_name=name)
        except Exception as e:
            error_msg = f"Unexpected error pushing metric {name}: {e}"
            logger.error(error_msg)
            raise PrometheusError(error_msg, metric_name=name)
    
    def _build_metric_data(self, name: str, labels: Dict[str, str], value: float, 
                          metric_type: str, help_text: str) -> str:
        """Prometheus exposition format でメトリクスデータを構築"""
        lines = []
        
        # HELP コメント
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
        
        # TYPE コメント
        lines.append(f"# TYPE {name} {metric_type}")
        
        # メトリクスデータ
        if labels:
            label_str = ','.join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {value}")
        else:
            lines.append(f"{name} {value}")
        
        return '\n'.join(lines) + '\n'
    
    def increment_counter(self, name: str, labels: Dict[str, str] = None, 
                         help_text: str = "") -> bool:
        """カウンターメトリクスを1増加"""
        return self.push_metric(
            name=name,
            labels=labels or {},
            value=1.0,
            metric_type="counter",
            help_text=help_text
        )
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None,
                 help_text: str = "") -> bool:
        """ゲージメトリクスを設定"""
        return self.push_metric(
            name=name,
            labels=labels or {},
            value=value,
            metric_type="gauge", 
            help_text=help_text
        )
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None,
                        help_text: str = "") -> bool:
        """ヒストグラムメトリクスを記録"""
        return self.push_metric(
            name=name,
            labels=labels or {},
            value=value,
            metric_type="histogram",
            help_text=help_text
        )


# グローバルインスタンス
_prometheus_client = None


def get_prometheus_client() -> PrometheusClient:
    """グローバル PrometheusClient インスタンスを取得"""
    global _prometheus_client
    if _prometheus_client is None:
        _prometheus_client = PrometheusClient()
    return _prometheus_client


def push_failure_metric(failure_type: str, error_message: str = "") -> bool:
    """監視失敗メトリクスを送信"""
    client = get_prometheus_client()
    
    labels = {
        "type": failure_type,
        "instance": os.getenv('HOSTNAME', 'localhost')
    }
    
    if error_message:
        # エラーメッセージのハッシュを追加（プライバシー保護のため）
        labels["error_hash"] = str(hash(error_message))[:8]
    
    return client.increment_counter(
        name="monitor_fail_total",
        labels=labels,
        help_text="Total number of monitoring failures by type"
    )


def push_monitoring_metric(items_processed: int, changes_found: int, 
                          duration_seconds: float) -> bool:
    """監視実行メトリクスを送信"""
    client = get_prometheus_client()
    
    instance_labels = {"instance": os.getenv('HOSTNAME', 'localhost')}
    
    # 処理アイテム数
    client.set_gauge(
        name="monitor_items_processed_total",
        value=items_processed,
        labels=instance_labels,
        help_text="Number of items processed in last monitoring run"
    )
    
    # 変更検出数
    client.set_gauge(
        name="monitor_changes_found_total", 
        value=changes_found,
        labels=instance_labels,
        help_text="Number of changes found in last monitoring run"
    )
    
    # 実行時間
    client.set_gauge(
        name="monitor_duration_seconds",
        value=duration_seconds,
        labels=instance_labels,
        help_text="Duration of last monitoring run in seconds"
    )
    
    return True


def push_database_metric(operation: str, success: bool, duration_ms: float = 0) -> bool:
    """データベース操作メトリクスを送信"""
    client = get_prometheus_client()
    
    labels = {
        "operation": operation,
        "status": "success" if success else "failure",
        "instance": os.getenv('HOSTNAME', 'localhost')
    }
    
    # 操作回数
    client.increment_counter(
        name="database_operations_total",
        labels=labels,
        help_text="Total number of database operations"
    )
    
    # 実行時間（成功時のみ）
    if success and duration_ms > 0:
        client.record_histogram(
            name="database_operation_duration_ms",
            value=duration_ms,
            labels={"operation": operation, "instance": labels["instance"]},
            help_text="Database operation duration in milliseconds"
        )
    
    return True
#!/usr/bin/env python3
"""Prometheus例外メトリクステスト"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exceptions import (
    LayoutChangeError, 
    DatabaseConnectionError, 
    ConfigurationError,
    DiscordNotificationError,
    PrometheusError,
    NetworkError
)

def test_exception_metrics():
    """例外発生時のメトリクス送信をテスト"""
    print("=== Exception Metrics Test ===")
    
    # テスト用例外を発生させる
    test_cases = [
        ("Layout Change", lambda: LayoutChangeError("Test layout change", "https://test.url")),
        ("Database Error", lambda: DatabaseConnectionError("Test DB error", "connect")),
        ("Config Error", lambda: ConfigurationError("Test config error", "config.json")),
        ("Discord Error", lambda: DiscordNotificationError("Test Discord error", 500, "Server Error")),
        ("Prometheus Error", lambda: PrometheusError("Test Prometheus error", "test_metric")),
        ("Network Error", lambda: NetworkError("Test network error", "https://test.com", True))
    ]
    
    for test_name, exception_func in test_cases:
        try:
            print(f"Testing {test_name}...")
            raise exception_func()
        except Exception as e:
            print(f"  ✅ Exception raised: {type(e).__name__}: {e}")
            # メトリクスの送信は例外内部で処理される
        
    print("\n✅ All exception metrics tests completed!")
    print("📊 Check Prometheus Pushgateway for 'monitor_exceptions_total' metric")
    print("💡 Metrics are only sent if PROM_PUSHGATEWAY_URL environment variable is set")

if __name__ == "__main__":
    test_exception_metrics()
"""
monitor.pyのランタイムインポートテスト
"""

import importlib


def test_monitor_imports():
    """monitor.pyが正常にインポートできることを確認"""
    importlib.import_module("monitor")

"""
monitor.pyのランタイムインポートテスト
"""

import pytest
from importlib import import_module


def test_monitor_imports():
    """monitor.pyが正常にインポートできることを確認"""
    try:
        import_module("monitor")
    except ModuleNotFoundError as e:
        pytest.fail(f"monitor.py import failed: {e}")


def test_monitor_run_once_function_exists():
    """run_monitor_once関数が存在することを確認"""
    monitor = import_module("monitor")
    assert hasattr(monitor, "run_monitor_once"), "run_monitor_once function not found"

    # 関数が呼び出し可能であることを確認
    assert callable(monitor.run_monitor_once), "run_monitor_once is not callable"


def test_monitor_run_function_exists():
    """run関数が存在することを確認"""
    monitor = import_module("monitor")
    assert hasattr(monitor, "run"), "run function not found"

    # 関数が呼び出し可能であることを確認
    assert callable(monitor.run), "run is not callable"


def test_monitor_send_notification_function_exists():
    """send_notification関数が存在することを確認"""
    monitor = import_module("monitor")
    assert hasattr(monitor, "send_notification"), "send_notification function not found"

    # 関数が呼び出し可能であることを確認
    assert callable(monitor.send_notification), "send_notification is not callable"


def test_monitor_discord_clients_exist():
    """Discord クライアントが正常に初期化されることを確認"""
    monitor = import_module("monitor")

    # プライベート変数として定義されているクライアントの存在確認
    assert hasattr(monitor, "_alert_client"), "_alert_client not found"
    assert hasattr(monitor, "_notification_client"), "_notification_client not found"

    # クライアントが DiscordClient インスタンスであることを確認
    from rakuten.discord_client import DiscordClient

    assert isinstance(monitor._alert_client, DiscordClient), (
        "_alert_client is not DiscordClient instance"
    )
    assert isinstance(monitor._notification_client, DiscordClient), (
        "_notification_client is not DiscordClient instance"
    )


def test_monitor_imports_no_discord_notifier():
    """monitor.pyが旧discord_notifierをインポートしていないことを確認"""
    import sys

    # 既にロードされている場合は削除
    if "monitor" in sys.modules:
        del sys.modules["monitor"]

    # インポート前にdiscord_notifierモジュールが存在しないことを確認
    with pytest.raises((ModuleNotFoundError, ImportError)):
        import_module("discord_notifier")

    # monitor.pyのインポートが成功することを確認
    monitor = import_module("monitor")
    assert monitor is not None

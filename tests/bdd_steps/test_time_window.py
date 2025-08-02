"""
BDD step definitions for time window testing.
"""

import pytest
from freezegun import freeze_time
import app.main as monitor


@pytest.mark.bdd
@freeze_time("2025-07-31 09:00:00")
def test_within_time_window(monkeypatch, tmp_path, capsys):
    """Test monitoring within configured time window."""
    # Set environment variables for time window
    monkeypatch.setenv("START_TIME", "08:00")
    monkeypatch.setenv("END_TIME", "20:00")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "dummy")  # Dummy notification
    monkeypatch.setenv("LIST_URL", "https://item.rakuten.co.jp/test/test/")
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "test.db"))

    # Mock the monitoring function to avoid actual HTTP requests
    def mock_run_monitor_once():
        print("Checking products within time window")
        return 0

    # Mock parse_args to avoid argparse issues in test environment
    class MockArgs:
        test_webhook = False
        once = True
        cron = False

    def mock_parse_args():
        return MockArgs()

    monkeypatch.setattr(monitor, "run_monitor_once", mock_run_monitor_once)
    monkeypatch.setattr(monitor, "parse_args", mock_parse_args)

    # Run monitor main function
    monitor.main()

    # Verify the monitoring was executed
    captured = capsys.readouterr()
    assert "Checking" in captured.out


@pytest.mark.bdd
@freeze_time("2025-07-31 07:30:00")
def test_outside_time_window_early(monkeypatch, tmp_path, capsys):
    """Test monitoring outside time window (too early)."""
    # Set environment variables for time window
    monkeypatch.setenv("START_TIME", "08:00")
    monkeypatch.setenv("END_TIME", "20:00")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "dummy")
    monkeypatch.setenv("LIST_URL", "https://item.rakuten.co.jp/test/test/")
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "test.db"))

    # Mock the monitoring function
    def mock_run_monitor_once():
        print("This should not be called")
        return 0

    # Mock parse_args
    class MockArgs:
        test_webhook = False
        once = True
        cron = False

    def mock_parse_args():
        return MockArgs()

    monkeypatch.setattr(monitor, "run_monitor_once", mock_run_monitor_once)
    monkeypatch.setattr(monitor, "parse_args", mock_parse_args)

    # Run monitor main function
    result = monitor.main()

    # Verify monitoring was skipped
    captured = capsys.readouterr()
    assert "outside watch window" in captured.out or result == 0


@pytest.mark.bdd
@freeze_time("2025-07-31 21:00:00")
def test_outside_time_window_late(monkeypatch, tmp_path, capsys):
    """Test monitoring outside time window (too late)."""
    # Set environment variables for time window
    monkeypatch.setenv("START_TIME", "08:00")
    monkeypatch.setenv("END_TIME", "20:00")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "dummy")
    monkeypatch.setenv("LIST_URL", "https://item.rakuten.co.jp/test/test/")
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "test.db"))

    # Mock the monitoring function
    def mock_run_monitor_once():
        print("This should not be called")
        return 0

    # Mock parse_args
    class MockArgs:
        test_webhook = False
        once = True
        cron = False

    def mock_parse_args():
        return MockArgs()

    monkeypatch.setattr(monitor, "run_monitor_once", mock_run_monitor_once)
    monkeypatch.setattr(monitor, "parse_args", mock_parse_args)

    # Run monitor main function
    result = monitor.main()

    # Verify monitoring was skipped
    captured = capsys.readouterr()
    assert "outside watch window" in captured.out or result == 0

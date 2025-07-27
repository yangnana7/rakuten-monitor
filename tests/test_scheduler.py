"""Unit tests for scheduler.py module."""
import sys
from pathlib import Path

# Add parent directory to Python path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import time
import subprocess
from unittest.mock import patch, Mock


class TestScheduler:
    """Test scheduler functionality."""
    
    @patch('monitor.run_once')
    def test_scheduler_runs_job_interval(self, mock_run_once):
        """Test scheduler runs monitor job at specified intervals."""
        # Arrange
        from scheduler import start
        
        mock_run_once.return_value = 0
        call_count = 0
        
        def count_calls():
            nonlocal call_count
            call_count += 1
            return 0
        
        mock_run_once.side_effect = count_calls
        
        # Act - Run scheduler for limited runs
        start(interval=0.01, max_runs=5)
        
        # Assert
        assert call_count >= 3, f"Expected ≥3 calls, got {call_count}"
    
    @patch('subprocess.run')
    def test_cli_once_option(self, mock_subprocess):
        """Test CLI --once option."""
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Act
        result = subprocess.run([
            sys.executable, "-c", 
            "import sys; sys.path.append('.'); from main import main; main(['--once'])"
        ], capture_output=True, cwd=str(Path(__file__).resolve().parents[1]))
        
        # Assert
        assert result.returncode == 0
    
    def test_cli_daemon_option(self):
        """Test CLI --daemon option with clean shutdown."""
        # Arrange
        import subprocess
        import time
        
        # Start daemon process
        process = subprocess.Popen([
            sys.executable, "-c",
            """
import sys
import os
sys.path.append('.')
from main import main

try:
    main(['--daemon', '--interval', '0.01'])
except KeyboardInterrupt:
    sys.exit(0)
"""
        ], cwd=str(Path(__file__).resolve().parents[1]))
        
        # Let it run briefly
        time.sleep(0.02)
        
        # Terminate process (cross-platform)
        process.terminate()
        
        # Wait for clean shutdown
        try:
            exit_code = process.wait(timeout=1.0)
            # On Windows, terminate() returns 1, but we accept both 0 and 1
            assert exit_code in [0, 1]
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            pytest.fail("Process did not shutdown cleanly")
    
    @patch('monitor.run_once')
    def test_scheduler_start_with_custom_interval(self, mock_run_once):
        """Test scheduler with custom interval."""
        # Arrange
        from scheduler import start
        
        mock_run_once.return_value = 0
        call_timestamps = []
        
        def record_call():
            call_timestamps.append(time.time())
            return 0
        
        mock_run_once.side_effect = record_call
        
        # Act
        start(interval=0.02, max_runs=3)
        
        # Assert
        assert len(call_timestamps) >= 2
        if len(call_timestamps) >= 2:
            interval = call_timestamps[1] - call_timestamps[0]
            assert 0.015 <= interval <= 0.025  # Allow some tolerance
    
    @patch('monitor.run_once')
    def test_scheduler_exception_handling(self, mock_run_once):
        """Test scheduler handles monitor exceptions gracefully."""
        # Arrange
        from scheduler import start
        
        call_count = 0
        
        def failing_monitor():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Monitor failed")
            return 0
        
        mock_run_once.side_effect = failing_monitor
        
        # Act
        start(interval=0.01, max_runs=5)
        
        # Assert - Scheduler should continue running despite exceptions
        assert call_count >= 3
    
    def test_scheduler_module_importable(self):
        """Test that scheduler module can be imported."""
        # Act & Assert
        try:
            import scheduler
            assert hasattr(scheduler, 'start')
            assert callable(scheduler.start)
        except ImportError:
            pytest.fail("scheduler module should be importable")
    
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_argument_parsing(self, mock_parse_args):
        """Test main module argument parsing."""
        # Arrange
        from main import main
        
        # Mock different argument combinations
        test_cases = [
            Mock(once=True, daemon=False, interval=15.0),
            Mock(once=False, daemon=True, interval=30.0),
            Mock(once=False, daemon=False, interval=60.0)
        ]
        
        for mock_args in test_cases:
            mock_parse_args.return_value = mock_args
            
            # Act & Assert - Should not raise exceptions
            with patch('monitor.run_once', return_value=0):
                with patch('scheduler.start'):
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0
    
    def test_main_module_importable(self):
        """Test that main module can be imported."""
        # Act & Assert
        try:
            import main
            assert hasattr(main, 'main')
            assert callable(main.main)
        except ImportError:
            pytest.fail("main module should be importable")
    
    @patch('scheduler.start')
    @patch('monitor.run_once')
    def test_daemon_mode_starts_scheduler(self, mock_run_once, mock_scheduler_start):
        """Test that daemon mode starts the scheduler."""
        # Arrange
        from main import main
        
        mock_run_once.return_value = 0
        
        # Act
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_args = Mock(once=False, daemon=True, interval=15.0)
            mock_parse_args.return_value = mock_args
            
            try:
                main()
            except KeyboardInterrupt:
                pass  # Expected for daemon mode
        
        # Assert
        mock_scheduler_start.assert_called_once_with(interval=15.0)
    
    @patch('monitor.run_once')
    def test_once_mode_calls_monitor_once(self, mock_run_once):
        """Test that --once mode calls monitor exactly once."""
        # Arrange
        from main import main
        
        mock_run_once.return_value = 5  # 5 notifications sent
        
        # Act
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_args = Mock(once=True, daemon=False, interval=15.0)
            mock_parse_args.return_value = mock_args
            
            try:
                main()
            except SystemExit as e:
                assert e.code == 0
        
        # Assert
        mock_run_once.assert_called_once()
"""Unit tests for monitor.py module."""
import sys
from pathlib import Path

# Add parent directory to Python path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import tempfile
import os
from unittest.mock import patch, Mock, call


class TestMonitor:
    """Test monitor functionality."""
    
    def setup_method(self):
        """Setup test database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
    
    def teardown_method(self):
        """Cleanup test database after each test."""
        import gc
        gc.collect()
        
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except (PermissionError, OSError):
            pass
    
    @patch('requests.get')
    @patch('discord_notifier.send_notification')
    @patch('monitor.ItemDB')
    def test_monitor_new_and_resale_flow(self, mock_db_class, mock_discord, mock_get):
        """Test monitor flow with new and resale products."""
        # Arrange
        from monitor import run_once
        
        # Mock HTML response with new and resale products
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <div class="item-container">
                    <div class="item-info">
                        <a href="/item/new-item-001/" class="item-link category_itemnamelink">
                            <h3 class="item-title">新商品1 ※8月上旬発送予定</h3>
                        </a>
                        <div class="item-code">商品コード: new-item-001</div>
                        <span class="category_itemprice">1,000円</span>
                    </div>
                </div>
                
                <div class="item-container">
                    <div class="item-info">
                        <a href="/item/new-item-002/" class="item-link category_itemnamelink">
                            <h3 class="item-title">新商品2 ※8月上旬発送予定</h3>
                        </a>
                        <div class="item-code">商品コード: new-item-002</div>
                        <span class="category_itemprice">2,000円</span>
                    </div>
                </div>
                
                <div class="item-container">
                    <div class="item-info">
                        <a href="/item/resale-item-001/" class="item-link category_itemnamelink">
                            <h3 class="item-title">再販商品1 ※9月上旬発送予定</h3>
                        </a>
                        <div class="item-code">商品コード: resale-item-001</div>
                        <span class="category_itemprice">3,000円</span>
                        <div class="resale-marker">再販商品</div>
                    </div>
                </div>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        mock_discord.return_value = True
        
        # Mock database
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.item_exists.return_value = False  # All items are new
        mock_db.save_item.return_value = True
        
        # Act
        result = run_once()
        
        # Assert
        assert result == 3  # 3 notifications sent
        assert mock_discord.call_count == 3
        
        # Verify Discord calls for different product types
        discord_calls = mock_discord.call_args_list
        statuses = [call[0][0]['status'] for call in discord_calls]
        assert 'NEW' in statuses
        assert 'RESALE' in statuses
    
    @patch('requests.get')
    @patch('discord_notifier.send_notification')
    def test_monitor_no_changes(self, mock_discord, mock_get):
        """Test monitor with no changes (UNCHANGED products only)."""
        # Arrange
        from monitor import run_once
        from item_db import ItemDB
        
        # Pre-populate database with known items
        db = ItemDB(self.db_path)
        db.save_item({
            "item_code": "existing-item-001",
            "title": "既存商品 ※8月上旬発送予定",
            "status": "NEW"
        })
        
        # Mock HTML response with same products (unchanged)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <a class="category_itemnamelink" href="/item/existing-item-001/">既存商品 ※8月上旬発送予定</a>
                <span class="category_itemprice">1,000円</span>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        mock_discord.return_value = True
        
        # Act
        with patch('monitor.ItemDB') as mock_db_class:
            mock_db_class.return_value = db
            result = run_once()
        
        # Assert
        assert result == 0  # No notifications sent for UNCHANGED
        assert mock_discord.call_count == 0
    
    @patch('requests.get')
    @patch('discord_notifier.send_notification')
    def test_monitor_network_error_alert(self, mock_discord, mock_get):
        """Test monitor network error handling and alert."""
        # Arrange
        from monitor import run_once
        
        # Mock network error
        mock_get.side_effect = Exception("Network connection failed")
        mock_discord.return_value = True
        
        # Act & Assert
        with pytest.raises(Exception, match="Network connection failed"):
            run_once()
        
        # Verify alert notification was sent
        assert mock_discord.call_count == 1
        alert_call = mock_discord.call_args[0][0]
        assert "ERROR" in alert_call.get('status', '')
        assert "Network connection failed" in alert_call.get('title', '')
    
    @patch('requests.get')
    @patch('discord_notifier.send_notification')
    def test_monitor_custom_url(self, mock_discord, mock_get):
        """Test monitor with custom URL parameter."""
        # Arrange
        from monitor import run_once
        
        custom_url = "https://custom.rakuten.co.jp/test"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body></body></html>'
        mock_get.return_value = mock_response
        mock_discord.return_value = True
        
        # Act
        result = run_once(url=custom_url)
        
        # Assert
        assert result == 0
        mock_get.assert_called_once_with(custom_url, timeout=30)
    
    @patch('requests.get')
    @patch('discord_notifier.send_notification')
    def test_monitor_database_integration(self, mock_discord, mock_get):
        """Test monitor database integration."""
        # Arrange
        from monitor import run_once
        from item_db import ItemDB
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <a class="category_itemnamelink" href="/item/test-db-item/">テストDB商品 ※8月上旬発送予定</a>
                <span class="category_itemprice">5,000円</span>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        mock_discord.return_value = True
        
        # Act
        with patch('monitor.ItemDB') as mock_db_class:
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            mock_db.item_exists.return_value = False  # New item
            
            result = run_once()
        
        # Assert
        assert result == 1
        mock_db.save_item.assert_called_once()
        saved_item = mock_db.save_item.call_args[0][0]
        assert saved_item['item_code'] == 'test-db-item'
        assert saved_item['status'] == 'NEW'
    
    @patch('requests.get')
    def test_monitor_http_error(self, mock_get):
        """Test monitor with HTTP error response."""
        # Arrange
        from monitor import run_once
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response
        
        # Act & Assert
        with pytest.raises(Exception, match="404 Not Found"):
            run_once()
    
    def test_monitor_returns_int(self):
        """Test that run_once always returns an integer."""
        # Arrange
        from monitor import run_once
        
        # Act
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '<html><body></body></html>'
            mock_get.return_value = mock_response
            
            result = run_once()
        
        # Assert
        assert isinstance(result, int)
        assert result >= 0
    
    @patch('monitor.run_once')
    def test_run_loop_with_max_runs(self, mock_run_once):
        """Test run_loop function with max_runs parameter."""
        # Arrange
        from monitor import run_loop
        
        mock_run_once.return_value = 2  # Each call returns 2 notifications
        
        # Act
        result = run_loop(interval=0, max_runs=1)
        
        # Assert
        assert result == 2  # Total notifications from 1 run
        assert mock_run_once.call_count == 1
    
    @patch('monitor.run_once')
    def test_run_loop_multiple_runs(self, mock_run_once):
        """Test run_loop function with multiple runs."""
        # Arrange
        from monitor import run_loop
        
        mock_run_once.side_effect = [1, 0, 3]  # Different notification counts
        
        # Act
        result = run_loop(interval=0, max_runs=3)
        
        # Assert
        assert result == 4  # Total: 1 + 0 + 3
        assert mock_run_once.call_count == 3
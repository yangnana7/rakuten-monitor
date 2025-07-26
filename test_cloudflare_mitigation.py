#!/usr/bin/env python3
"""
Cloudflare対策機能のテスト
"""

import pytest
import requests_mock
from unittest.mock import patch, MagicMock, AsyncMock
from fetch_items import (
    fetch_with_cloudscraper, 
    fetch_with_playwright, 
    fetch_with_retry,
    LIST_URL
)

class TestCloudflareBypass:
    
    def test_fetch_with_cloudscraper_success(self):
        """cloudscraper成功テスト"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><a class='category_itemnamelink'>Test</a></body></html>"
        
        with patch('cloudscraper.create_scraper') as mock_scraper:
            mock_scraper.return_value.get.return_value = mock_response
            
            result = fetch_with_cloudscraper(LIST_URL)
            
            assert result is not None
            assert result.status_code == 200
            mock_scraper.assert_called_once()

    def test_fetch_with_cloudscraper_challenge_error(self):
        """cloudscraper Cloudflareチャレンジエラーテスト"""
        import cloudscraper
        
        with patch('cloudscraper.create_scraper') as mock_scraper:
            mock_scraper.return_value.get.side_effect = cloudscraper.exceptions.CloudflareChallengeError("Challenge")
            
            result = fetch_with_cloudscraper(LIST_URL)
            
            assert result is None

    def test_fetch_with_cloudscraper_general_error(self):
        """cloudscraper 一般エラーテスト"""
        with patch('cloudscraper.create_scraper') as mock_scraper:
            mock_scraper.return_value.get.side_effect = Exception("Network error")
            
            result = fetch_with_cloudscraper(LIST_URL)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_playwright_success(self):
        """playwright成功テスト"""
        mock_content = "<html><body><a class='category_itemnamelink'>Test Product</a></body></html>"
        
        # Playwrightが利用可能な場合のみテスト
        with patch('fetch_items.PLAYWRIGHT_AVAILABLE', True):
            with patch('fetch_items.async_playwright') as mock_playwright:
                # async contextmanager のモック
                mock_p = AsyncMock()
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_page.content.return_value = mock_content
                mock_context.new_page.return_value = mock_page
                mock_browser.new_context.return_value = mock_context
                mock_p.chromium.launch.return_value = mock_browser
                
                mock_playwright.return_value.__aenter__.return_value = mock_p
                
                result = await fetch_with_playwright(LIST_URL)
                
                assert result == mock_content
                mock_p.chromium.launch.assert_called_once()

    @pytest.mark.asyncio  
    async def test_fetch_with_playwright_not_available(self):
        """playwright未インストール時のテスト"""
        with patch('fetch_items.PLAYWRIGHT_AVAILABLE', False):
            result = await fetch_with_playwright(LIST_URL)
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_playwright_error(self):
        """playwright実行エラーテスト"""
        with patch('fetch_items.PLAYWRIGHT_AVAILABLE', True):
            with patch('fetch_items.async_playwright') as mock_playwright:
                mock_playwright.side_effect = Exception("Browser launch failed")
                
                result = await fetch_with_playwright(LIST_URL)
                
                assert result is None

    @requests_mock.Mocker()
    def test_fetch_with_retry_requests_success(self, m):
        """fetch_with_retry - requests成功テスト"""
        m.get(LIST_URL, text="<html><body>Success</body></html>", status_code=200)
        
        result = fetch_with_retry(LIST_URL)
        
        assert result is not None
        assert result.status_code == 200

    @requests_mock.Mocker() 
    def test_fetch_with_retry_requests_fail_cloudscraper_success(self, m):
        """fetch_with_retry - requests失敗→cloudscraper成功テスト"""
        # requests は失敗
        m.get(LIST_URL, exc=requests_mock.exceptions.ConnectionError)
        
        # cloudscraper は成功
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Success via cloudscraper</body></html>"
        
        with patch('fetch_items.fetch_with_cloudscraper', return_value=mock_response):
            result = fetch_with_retry(LIST_URL)
            
            assert result is not None
            assert result.status_code == 200

    def test_fetch_with_retry_all_methods_fail(self):
        """fetch_with_retry - 全メソッド失敗テスト"""
        with patch('fetch_items.create_session_with_retry') as mock_session:
            mock_session.return_value.get.side_effect = Exception("Network error")
            
            with patch('fetch_items.fetch_with_cloudscraper', return_value=None):
                with patch('fetch_items.fetch_with_playwright') as mock_playwright:
                    with patch('asyncio.new_event_loop') as mock_loop:
                        mock_loop.return_value.run_until_complete.return_value = None
                        
                        result = fetch_with_retry(LIST_URL)
                        
                        assert result is None

    def test_fetch_with_retry_playwright_fallback_success(self):
        """fetch_with_retry - playwright フォールバック成功テスト"""
        # requests と cloudscraper は失敗
        with patch('fetch_items.create_session_with_retry') as mock_session:
            mock_session.return_value.get.side_effect = Exception("Network error")
            
            with patch('fetch_items.fetch_with_cloudscraper', return_value=None):
                with patch('asyncio.new_event_loop') as mock_loop:
                    mock_loop_instance = MagicMock()
                    mock_loop.return_value = mock_loop_instance
                    mock_loop_instance.run_until_complete.return_value = "<html><body>Playwright success</body></html>"
                    
                    result = fetch_with_retry(LIST_URL)
                    
                    assert result is not None
                    assert "Playwright success" in result.text

    def test_mock_response_class(self):
        """MockResponseクラスのテスト"""
        from fetch_items import fetch_with_retry
        
        # Playwright成功時のMockResponseをテスト
        with patch('fetch_items.create_session_with_retry') as mock_session:
            mock_session.return_value.get.side_effect = Exception("Network error")
            
            with patch('fetch_items.fetch_with_cloudscraper', return_value=None):
                with patch('asyncio.new_event_loop') as mock_loop:
                    mock_loop_instance = MagicMock()
                    mock_loop.return_value = mock_loop_instance
                    mock_loop_instance.run_until_complete.return_value = "<html><body>Test</body></html>"
                    
                    result = fetch_with_retry(LIST_URL)
                    
                    assert result is not None
                    assert result.status_code == 200
                    assert result.text == "<html><body>Test</body></html>"
                    
                    # raise_for_status のテスト
                    result.raise_for_status()  # 200なのでエラーにならない

    @patch('fetch_items.record_fetch_attempt')
    def test_metrics_recording(self, mock_record):
        """メトリクス記録のテスト"""
        with requests_mock.Mocker() as m:
            m.get(LIST_URL, text="<html><body>Success</body></html>", status_code=200)
            
            result = fetch_with_retry(LIST_URL)
            
            assert result is not None
            # メトリクス記録が呼ばれたことを確認
            mock_record.assert_called()
            args, kwargs = mock_record.call_args
            assert args[0] == 'requests'  # method
            assert args[1] is True        # success

    @patch('fetch_items.record_fetch_attempt')
    def test_metrics_recording_failure(self, mock_record):
        """メトリクス記録（失敗時）のテスト"""
        with patch('fetch_items.create_session_with_retry') as mock_session:
            mock_session.return_value.get.side_effect = Exception("Network error")
            
            with patch('fetch_items.fetch_with_cloudscraper', return_value=None):
                with patch('asyncio.new_event_loop') as mock_loop:
                    mock_loop.return_value.run_until_complete.return_value = None
                    
                    result = fetch_with_retry(LIST_URL)
                    
                    assert result is None
                    # 失敗時のメトリクス記録が呼ばれたことを確認
                    mock_record.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
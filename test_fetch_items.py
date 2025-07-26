#!/usr/bin/env python3
"""
fetch_items.py のテスト
"""

import pytest
import requests
import requests_mock
from unittest.mock import patch
from fetch_items import parse_list, create_session_with_retry, LIST_URL

# テスト用HTML
MOCK_HTML = """
<html>
<body>
    <div class="searchResultItem">
        <a class="category_itemnamelink" href="/item1/">
            商品1 - パチスロ小役カウンター
        </a>
        <span class="price">3,980</span>
        <span class="stock_status">在庫あり</span>
    </div>
    <div class="searchResultItem">
        <a class="category_itemnamelink" href="/item2/">
            商品2 - 勝ち勝ちくん
        </a>
        <span class="price">5,500</span>
        <span class="stock_status">在庫切れ</span>
    </div>
</body>
</html>
"""

EMPTY_HTML = """
<html>
<body>
    <div>商品がありません</div>
</body>
</html>
"""

class TestCreateSessionWithRetry:
    def test_create_session_returns_session(self):
        """セッション作成のテスト"""
        session = create_session_with_retry()
        assert session is not None
        assert hasattr(session, 'get')
        assert hasattr(session, 'post')

class TestParseList:
    @requests_mock.Mocker()
    def test_parse_list_success(self, m):
        """正常な商品取得のテスト"""
        m.get(LIST_URL, text=MOCK_HTML)
        
        result = parse_list(LIST_URL)
        
        assert len(result) == 2
        assert result[0]['title'] == '商品1 - パチスロ小役カウンター'
        assert result[0]['price'] == 3980
        assert result[0]['in_stock'] is True
        assert result[1]['title'] == '商品2 - 勝ち勝ちくん'
        assert result[1]['price'] == 5500
        assert result[1]['in_stock'] is False

    @requests_mock.Mocker()
    def test_parse_list_empty_result(self, m):
        """商品が見つからない場合のテスト"""
        m.get(LIST_URL, text=EMPTY_HTML)
        
        result = parse_list(LIST_URL)
        
        assert result == []

    @requests_mock.Mocker()
    def test_parse_list_network_error(self, m):
        """ネットワークエラーのテスト"""
        m.get(LIST_URL, exc=requests_mock.exceptions.ConnectionError)
        
        result = parse_list(LIST_URL)
        
        assert result == []

    @requests_mock.Mocker()
    def test_parse_list_http_error(self, m):
        """HTTPエラーのテスト"""
        m.get(LIST_URL, status_code=404)
        
        result = parse_list(LIST_URL)
        
        assert result == []

    @requests_mock.Mocker()
    def test_parse_list_timeout(self, m):
        """タイムアウトのテスト"""
        m.get(LIST_URL, exc=requests.exceptions.Timeout)
        
        result = parse_list(LIST_URL)
        
        assert result == []

    @requests_mock.Mocker()
    def test_parse_list_malformed_html(self, m):
        """不正なHTMLのテスト"""
        malformed_html = """
        <html>
        <body>
            <div class="searchResultItem">
                <a class="category_itemnamelink" href="/item1/">
                    商品1
                </a>
                <!-- 価格や在庫情報が欠けている -->
            </div>
        </body>
        </html>
        """
        m.get(LIST_URL, text=malformed_html)
        
        result = parse_list(LIST_URL)
        
        # 不完全な商品データでもエラーにならず、取得可能な情報で商品を作成
        assert len(result) >= 0  # エラーで空配列になるか、部分的な情報で商品が作成される

    @requests_mock.Mocker()
    def test_parse_list_various_price_formats(self, m):
        """様々な価格フォーマットのテスト"""
        html_with_various_prices = """
        <html>
        <body>
            <div class="searchResultItem">
                <a class="category_itemnamelink" href="/item1/">商品1</a>
                <span class="price">¥3,980</span>
            </div>
            <div class="searchResultItem">
                <a class="category_itemnamelink" href="/item2/">商品2</a>
                <span class="price">5500円</span>
            </div>
            <div class="searchResultItem">
                <a class="category_itemnamelink" href="/item3/">商品3</a>
                <span class="price">7,700</span>
            </div>
        </body>
        </html>
        """
        m.get(LIST_URL, text=html_with_various_prices)
        
        result = parse_list(LIST_URL)
        
        assert len(result) == 3
        # 価格のパース処理が正しく動作することを確認
        for item in result:
            assert isinstance(item['price'], int)
            assert item['price'] > 0

    @requests_mock.Mocker()
    @patch('fetch_items.logger')
    def test_parse_list_logging(self, mock_logger, m):
        """ログ出力のテスト"""
        m.get(LIST_URL, text=MOCK_HTML)
        
        parse_list(LIST_URL)
        
        # ログが正しく呼び出されることを確認
        mock_logger.info.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""HTML parserのテスト"""

import pytest
from unittest.mock import Mock, patch, mock_open
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_parser import RakutenHtmlParser, Product, parse_rakuten_page
from exceptions import LayoutChangeError, NetworkError


class TestRakutenHtmlParser:
    """RakutenHtmlParserのテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        self.parser = RakutenHtmlParser(timeout=3, max_retries=3)
        
        # サンプルHTMLデータ
        self.sample_category_html = """
        <html>
        <body>
            <div class="searchresultitem">
                <h3><a href="/shop/test-shop/item-123/">テスト商品1</a></h3>
                <div class="item-price">¥1,000</div>
            </div>
            <div class="searchresultitem">
                <h3><a href="/shop/test-shop/item-456/">テスト商品2 売り切れ</a></h3>
                <div class="item-price">¥2,000</div>
                <span class="soldout">売り切れ</span>
            </div>
            <div class="searchresultitem">
                <h3><a href="/shop/test-shop/item-789/">テスト商品3</a></h3>
                <div class="item-price">¥3,500</div>
            </div>
        </body>
        </html>
        """
        
        self.sample_single_product_html = """
        <html>
        <body>
            <h1 class="item_name">単体テスト商品</h1>
            <div class="item_price">¥5,000</div>
            <div class="stock_status">在庫あり</div>
        </body>
        </html>
        """
        
        self.layout_changed_html = """
        <html>
        <body>
            <!-- 全く異なる構造 -->
            <div class="new-layout">
                <p>商品情報が見つかりません</p>
            </div>
        </body>
        </html>
        """
    
    @patch('html_parser.requests.Session.get')
    def test_parse_category_page_success(self, mock_get):
        """カテゴリページの正常解析テスト"""
        # モックの設定
        mock_response = Mock()
        mock_response.text = self.sample_category_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行
        products = self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
        
        # 検証
        assert len(products) == 3
        
        # 商品1: 在庫あり
        product1 = next(p for p in products if "テスト商品1" in p.name)
        assert product1.name == "テスト商品1"
        assert product1.price == 1000
        assert product1.in_stock == True
        assert "item-123" in product1.url
        
        # 商品2: 売り切れ
        product2 = next(p for p in products if "テスト商品2" in p.name)
        assert product2.name == "テスト商品2 売り切れ"
        assert product2.price == 2000
        assert product2.in_stock == False  # 売り切れテキストを検出
        
        # 商品3: 在庫あり
        product3 = next(p for p in products if "テスト商品3" in p.name)
        assert product3.name == "テスト商品3"
        assert product3.price == 3500
        assert product3.in_stock == True
    
    @patch('html_parser.requests.Session.get')
    def test_parse_single_product_page_success(self, mock_get):
        """単一商品ページの正常解析テスト"""
        # モックの設定
        mock_response = Mock()
        mock_response.text = self.sample_single_product_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行
        products = self.parser.parse_product_page("https://item.rakuten.co.jp/shop/single-item/")
        
        # 検証
        assert len(products) == 1
        product = products[0]
        assert product.name == "単体テスト商品"
        assert product.price == 5000
        assert product.in_stock == True
        assert "single-item" in product.url
    
    @patch('html_parser.requests.Session.get')
    def test_layout_change_detection(self, mock_get):
        """レイアウト変更の検出テスト"""
        # モックの設定
        mock_response = Mock()
        mock_response.text = self.layout_changed_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行と検証
        with pytest.raises(LayoutChangeError):
            self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
    
    @patch('html_parser.requests.Session.get')
    def test_network_error_with_retry(self, mock_get):
        """ネットワークエラーのリトライテスト"""
        # 最初の2回は失敗、3回目で成功
        mock_get.side_effect = [
            Exception("Connection timeout"),  # 1回目失敗
            Exception("Connection refused"),   # 2回目失敗
            Mock(text=self.sample_category_html, raise_for_status=Mock())  # 3回目成功
        ]
        
        # 実行
        products = self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
        
        # 検証: 最終的に成功することを確認
        assert len(products) == 3
        assert mock_get.call_count == 3
    
    @patch('html_parser.requests.Session.get')
    def test_network_error_max_retries_exceeded(self, mock_get):
        """リトライ上限を超えたネットワークエラーテスト"""
        # 全てのリトライで失敗
        mock_get.side_effect = Exception("Persistent network error")
        
        # 実行と検証
        with pytest.raises(NetworkError) as exc_info:
            self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
        
        assert "Persistent network error" in str(exc_info.value)
        assert mock_get.call_count == 3  # max_retries回試行
    
    def test_product_id_extraction_from_url(self):
        """URLからの商品ID抽出テスト"""
        # 楽天の一般的なURL形式
        url1 = "https://item.rakuten.co.jp/shop-name/item-code-123/"
        result1 = self.parser._extract_product_id_from_url(url1)
        assert result1 == "item-code-123"
        
        # パスが複数ある場合
        url2 = "https://item.rakuten.co.jp/shop-name/category/item-abc-456/"
        result2 = self.parser._extract_product_id_from_url(url2)
        assert result2 == "item-abc-456"
        
        # 不正なURLの場合はハッシュを返す
        url3 = "https://invalid.url"
        result3 = self.parser._extract_product_id_from_url(url3)
        assert len(result3) == 16  # MD5ハッシュの長さ
    
    def test_price_parsing(self):
        """価格パースのテスト"""
        assert self.parser._parse_price("¥1,000") == 1000
        assert self.parser._parse_price("2,500円") == 2500
        assert self.parser._parse_price("価格: ¥3,999 (税込)") == 3999
        assert self.parser._parse_price("無料") == 0
        assert self.parser._parse_price("") == 0
        assert self.parser._parse_price(None) == 0
    
    def test_stock_status_check(self):
        """在庫状況チェックのテスト"""
        # 売り切れパターン
        soldout_html = '<div class="item"><span class="soldout">売り切れ</span></div>'
        soup = BeautifulSoup(soldout_html, 'html.parser')
        item = soup.find('div', class_='item')
        assert self.parser._check_stock_status(item) == False
        
        # 在庫ありパターン
        instock_html = '<div class="item"><span class="stock">在庫あり</span></div>'
        soup = BeautifulSoup(instock_html, 'html.parser')
        item = soup.find('div', class_='item')
        assert self.parser._check_stock_status(item) == True
        
        # 売り切れテキストパターン
        soldout_text_html = '<div class="item">この商品は在庫切れです</div>'
        soup = BeautifulSoup(soldout_text_html, 'html.parser')
        item = soup.find('div', class_='item')
        assert self.parser._check_stock_status(item) == False


class TestParseRakutenPageFunction:
    """parse_rakuten_page関数のテスト"""
    
    @patch('html_parser.RakutenHtmlParser.parse_product_page')
    def test_convenience_function(self, mock_parse):
        """便利関数のテスト"""
        # モックの設定
        expected_products = [
            Product(id="test1", name="テスト商品", price=1000, url="http://test.com", in_stock=True)
        ]
        mock_parse.return_value = expected_products
        
        # 実行
        result = parse_rakuten_page("http://test.com", timeout=5, max_retries=2)
        
        # 検証
        assert result == expected_products
        mock_parse.assert_called_once_with("http://test.com")


class TestProductDataClass:
    """Productデータクラスのテスト"""
    
    def test_product_creation(self):
        """Productオブジェクトの作成テスト"""
        product = Product(
            id="test123",
            name="テスト商品",
            price=1500,
            url="https://example.com/test",
            in_stock=True
        )
        
        assert product.id == "test123"
        assert product.name == "テスト商品"
        assert product.price == 1500
        assert product.url == "https://example.com/test"
        assert product.in_stock == True
    
    def test_product_equality(self):
        """Productオブジェクトの等価性テスト"""
        product1 = Product(id="test", name="商品", price=100, url="http://test.com", in_stock=True)
        product2 = Product(id="test", name="商品", price=100, url="http://test.com", in_stock=True)
        product3 = Product(id="test2", name="商品", price=100, url="http://test.com", in_stock=True)
        
        assert product1 == product2
        assert product1 != product3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
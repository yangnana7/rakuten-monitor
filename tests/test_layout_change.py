"""HTML構造変更検出のテスト"""

import pytest
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_parser import RakutenHtmlParser
from exceptions import LayoutChangeError
from monitor import RakutenMonitor


class TestLayoutChangeDetection:
    """HTML構造変更検出のテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される準備処理"""
        self.parser = RakutenHtmlParser()
        
        # 正常なHTMLサンプル
        self.normal_html = """
        <html>
        <body>
            <div class="searchresultitem">
                <h3><a href="/shop/test/item1/">商品1</a></h3>
                <div class="item-price">¥1,000</div>
            </div>
            <div class="searchresultitem">
                <h3><a href="/shop/test/item2/">商品2</a></h3>
                <div class="item-price">¥2,000</div>
            </div>
        </body>
        </html>
        """
        
        # 構造が変更されたHTML（カテゴリページとして認識されるが商品要素がない）
        self.layout_changed_html = """
        <html>
        <body>
            <div class="searchresultitem">
                <!-- 商品要素があるように見えるが、実際には必要な子要素がない -->
                <div class="new-design">
                    <h1>サイトリニューアル中</h1>
                    <p>商品情報は準備中です</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # 部分的に構造が変更されたHTML（カテゴリページとして認識されるが商品情報が不完全）
        self.partial_layout_change = """
        <html>
        <body>
            <div class="searchresultitem">
                <!-- URLがないリンク -->
                <h2><a>商品1</a></h2>  
                <!-- 価格要素のクラスが完全に変更されて抽出できない -->
                <span class="unknown-price-format">¥1,000</span>    
            </div>
        </body>
        </html>
        """
        
        # 空のHTML
        self.empty_html = """
        <html>
        <body>
        </body>
        </html>
        """
    
    @patch('html_parser.requests.Session.get')
    def test_layout_change_no_items_found(self, mock_get):
        """商品要素が見つからない場合のLayoutChangeError発生テスト"""
        # 構造が変更されたHTMLを返すモック
        mock_response = Mock()
        mock_response.text = self.layout_changed_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行と検証
        with pytest.raises(LayoutChangeError) as exc_info:
            self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
        
        assert "商品情報を抽出できませんでした" in str(exc_info.value)
    
    @patch('html_parser.requests.Session.get')
    def test_layout_change_no_product_info_extracted(self, mock_get):
        """商品情報が抽出できない場合のLayoutChangeError発生テスト"""
        # 部分的に構造が変更されたHTMLを返すモック
        mock_response = Mock()
        mock_response.text = self.partial_layout_change
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行と検証
        with pytest.raises(LayoutChangeError) as exc_info:
            self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
        
        assert "商品情報を抽出できませんでした" in str(exc_info.value)
    
    @patch('html_parser.requests.Session.get')
    def test_layout_change_empty_page(self, mock_get):
        """空のページに対するLayoutChangeError発生テスト"""
        # 空のHTMLを返すモック
        mock_response = Mock()
        mock_response.text = self.empty_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行と検証
        with pytest.raises(LayoutChangeError):
            self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
    
    @patch('html_parser.requests.Session.get')
    def test_single_product_layout_change(self, mock_get):
        """単一商品ページの構造変更テスト"""
        # 単一商品ページで構造が変更されたHTMLを返すモック
        invalid_single_product_html = """
        <html>
        <body>
            <div class="new-product-layout">
                <p>商品詳細ページは準備中です</p>
            </div>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = invalid_single_product_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行と検証
        with pytest.raises(LayoutChangeError) as exc_info:
            self.parser.parse_product_page("https://item.rakuten.co.jp/shop/item123/")
        
        assert "単一商品ページの解析に失敗" in str(exc_info.value)
    
    @patch('html_parser.requests.Session.get')
    def test_normal_html_no_layout_error(self, mock_get):
        """正常なHTMLではLayoutChangeErrorが発生しないことのテスト"""
        # 正常なHTMLを返すモック
        mock_response = Mock()
        mock_response.text = self.normal_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 実行（例外が発生しないことを確認）
        try:
            products = self.parser.parse_product_page("https://search.rakuten.co.jp/search/mall/test/")
            assert len(products) == 2  # 正常に2つの商品が抽出される
        except LayoutChangeError:
            pytest.fail("Normal HTML should not raise LayoutChangeError")
    
    def test_selector_fallback_mechanism(self):
        """セレクタのフォールバック機能テスト"""
        # 複数のセレクタパターンをテスト
        from bs4 import BeautifulSoup
        
        # 古いセレクタパターン
        old_pattern_html = """
        <div class="old-item-class">
            <h3><a href="/item1">商品1</a></h3>
            <div class="old-price-class">¥1,000</div>
        </div>
        """
        
        # 新しいセレクタパターン  
        new_pattern_html = """
        <div class="item-grid">
            <h3><a href="/item1">商品1</a></h3>
            <div class="price">¥1,000</div>
        </div>
        """
        
        soup_old = BeautifulSoup(old_pattern_html, 'html.parser')
        soup_new = BeautifulSoup(new_pattern_html, 'html.parser')
        
        # いずれかのパターンで商品名が抽出できることを確認
        old_item = soup_old.find('div')
        new_item = soup_new.find('div')
        
        name_selectors = ['.item-name a', '.item-title a', 'h3 a', 'h2 a']
        
        old_name = self.parser._extract_text_by_selectors(old_item, name_selectors)
        new_name = self.parser._extract_text_by_selectors(new_item, name_selectors)
        
        assert old_name == "商品1"
        assert new_name == "商品1"


class TestMonitorLayoutChangeHandling:
    """Monitor統合でのレイアウト変更処理テスト"""
    
    def setup_method(self):
        """テスト準備"""
        self.monitor = RakutenMonitor()
    
    @patch('monitor.push_failure_metric')
    def test_layout_change_error_handling_in_monitor(self, mock_push_metric):
        """MonitorでのLayoutChangeError処理テスト"""
        # HTML parserをモック
        with patch.object(self.monitor, 'html_parser') as mock_html_parser:
            mock_html_parser.parse_product_page.side_effect = LayoutChangeError("Layout changed")
            
            # 実行と検証
            with pytest.raises(LayoutChangeError):
                self.monitor.process_url_with_diff("https://test.url")
            
            # Prometheusメトリクスが送信されることを確認
            mock_push_metric.assert_called_once_with("layout", "Layout change detected for https://test.url")
    
    @patch('monitor.push_failure_metric')
    @patch('monitor.DiscordNotifier')
    def test_layout_change_discord_notification(self, mock_discord_notifier, mock_push_metric):
        """レイアウト変更時のDiscord通知テスト"""
        # モックの設定
        mock_notifier_instance = Mock()
        mock_discord_notifier.return_value = mock_notifier_instance
        
        # 設定をモック
        config = {
            'urls': ['https://test.url'],
            'webhookUrl': 'https://discord.com/webhook'
        }
        
        # HTML parserをモック
        with patch.object(self.monitor, 'html_parser') as mock_html_parser:
            mock_html_parser.parse_product_page.side_effect = LayoutChangeError("HTML structure changed")
            
            with patch.object(self.monitor, '_is_monitoring_time', return_value=True):
                with patch.object(self.monitor.config_loader, 'load_config', return_value=config):
                    # 実行
                    self.monitor.run_monitoring_with_diff()
        
        # Discord通知が送信されることを確認
        mock_notifier_instance.send_critical.assert_called_once()
        call_args = mock_notifier_instance.send_critical.call_args
        assert "HTML構造変更検出" in call_args[1]['title']
        assert "楽天ページの構造が変更された" in call_args[1]['message']
    
    def test_layout_change_recovery_after_fix(self):
        """レイアウト変更後の回復テスト"""
        from html_parser import Product
        
        # HTML parserをモック
        with patch.object(self.monitor, 'html_parser') as mock_html_parser:
            # 最初はLayoutChangeError、次回は正常
            mock_html_parser.parse_product_page.side_effect = [
                LayoutChangeError("Layout changed"),
                [Product(id="test", name="テスト商品", price=1000, url="https://test.com", in_stock=True)]
            ]
            
            # 1回目: エラー
            with pytest.raises(LayoutChangeError):
                self.monitor.process_url_with_diff("https://test.url")
            
            # 2回目: 成功
            diff_result = self.monitor.process_url_with_diff("https://test.url")
            assert len(diff_result.new_items) == 1


class TestLayoutChangeMetrics:
    """レイアウト変更メトリクスのテスト"""
    
    @patch('monitor.push_failure_metric')
    def test_layout_change_metrics_increment(self, mock_push_metric):
        """レイアウト変更メトリクスの増分テスト"""
        monitor = RakutenMonitor()
        
        with patch.object(monitor.html_parser, 'parse_product_page') as mock_parse:
            mock_parse.side_effect = LayoutChangeError("Layout changed")
            
            # 複数回エラーを発生させる
            for i in range(3):
                with pytest.raises(LayoutChangeError):
                    monitor.process_url_with_diff(f"https://test{i}.url")
        
        # メトリクスが3回送信されることを確認
        assert mock_push_metric.call_count == 3
        
        # 各呼び出しでlayoutタイプが指定されることを確認
        for call in mock_push_metric.call_args_list:
            assert call[0][0] == "layout"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
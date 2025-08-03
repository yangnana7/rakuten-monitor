"""楽天商品監視ツール メインCLI"""
import argparse
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
import re

from .config_loader import ConfigLoader
from .item_db import ItemDatabase, LegacyJSONDatabase
from .discord_notifier import DiscordNotifier
from .exceptions import (
    RakutenMonitorError, 
    LayoutChangeError, 
    DatabaseConnectionError,
    ConfigurationError,
    DiscordNotificationError
)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RakutenMonitor:
    """楽天商品監視ツールのメインクラス"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_loader = ConfigLoader(config_path)
        self.db = ItemDatabase()
        self.notifier = None
        self._migrate_legacy_data()
    
    def _migrate_legacy_data(self) -> None:
        """database.jsonからSQLiteへデータ移行"""
        try:
            legacy_db = LegacyJSONDatabase()
            migrated_count = legacy_db.migrate_to_sqlite(self.db)
            if migrated_count > 0:
                logger.info(f"Migrated {migrated_count} items from legacy database")
        except Exception as e:
            logger.warning(f"Legacy data migration failed: {e}")
    
    def _is_monitoring_time(self) -> bool:
        """現在時刻が監視時間内かチェック"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        start_time = self.config_loader.start_time
        end_time = self.config_loader.end_time
        
        return start_time <= current_time <= end_time
    
    def _extract_product_info(self, url: str, html: str) -> List[Dict[str, Any]]:
        """HTMLから商品情報を抽出"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            products = []
            
            # 楽天市場の商品ページパターン（簡易版）
            if '/item.rakuten.co.jp/' in url:
                # 単一商品ページ
                product = self._extract_single_product(soup, url)
                if product:
                    products.append(product)
            else:
                # カテゴリページ - 複数商品
                products = self._extract_multiple_products(soup, url)
            
            if not products:
                raise LayoutChangeError(f"商品情報を抽出できませんでした: {url}")
            
            return products
            
        except Exception as e:
            if isinstance(e, LayoutChangeError):
                raise
            raise LayoutChangeError(f"HTML解析エラー: {e}")
    
    def _extract_single_product(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """単一商品ページから情報抽出"""
        try:
            # 商品名
            name_selectors = [
                'h1[data-testid="item-name"]',
                '.item_name h1',
                'h1.item_name',
                'h1'
            ]
            name = self._find_text_by_selectors(soup, name_selectors)
            
            # 価格
            price_selectors = [
                '[data-testid="price"]',
                '.price_value',
                '.price',
                '.item_price'
            ]
            price = self._find_text_by_selectors(soup, price_selectors)
            
            # 在庫状況
            stock_selectors = [
                '[data-testid="stock-status"]',
                '.item_stock',
                '.stock_status'
            ]
            stock_text = self._find_text_by_selectors(soup, stock_selectors)
            
            # 在庫状況の判定
            if stock_text and any(keyword in stock_text for keyword in ['売り切れ', '在庫なし', '品切れ']):
                status = '売り切れ'
            else:
                status = '在庫あり'
            
            # 商品IDを生成（URLから）
            product_id = self._extract_product_id_from_url(url)
            
            return {
                'product_id': product_id,
                'name': name or 'Unknown Product',
                'price': price or '価格不明',
                'status': status,
                'url': url
            }
            
        except Exception as e:
            logger.warning(f"Single product extraction failed: {e}")
            return None
    
    def _extract_multiple_products(self, soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
        """カテゴリページから複数商品情報抽出"""
        products = []
        
        # 楽天市場のカテゴリページの商品アイテム
        item_selectors = [
            '.searchresultitem',
            '.item',
            '.product'
        ]
        
        items = []
        for selector in item_selectors:
            items = soup.select(selector)
            if items:
                break
        
        for item in items[:20]:  # 最大20件に制限
            try:
                # 商品リンク
                link_elem = item.select_one('a[href*="/item.rakuten.co.jp/"]')
                if not link_elem:
                    continue
                
                product_url = link_elem.get('href')
                if not product_url.startswith('http'):
                    product_url = 'https:' + product_url
                
                # 商品名
                name_elem = item.select_one('.itemname, .item_name, h3')
                name = name_elem.get_text(strip=True) if name_elem else 'Unknown Product'
                
                # 価格
                price_elem = item.select_one('.price, .item_price')
                price = price_elem.get_text(strip=True) if price_elem else '価格不明'
                
                # 在庫状況（簡易判定）
                item_text = item.get_text()
                if any(keyword in item_text for keyword in ['売り切れ', '在庫なし', '品切れ']):
                    status = '売り切れ'
                else:
                    status = '在庫あり'
                
                product_id = self._extract_product_id_from_url(product_url)
                
                products.append({
                    'product_id': product_id,
                    'name': name,
                    'price': price,
                    'status': status,
                    'url': product_url
                })
                
            except Exception as e:
                logger.warning(f"Failed to extract product from item: {e}")
                continue
        
        return products
    
    def _find_text_by_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """複数のセレクタから最初にマッチするテキストを取得"""
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return ""
    
    def _extract_product_id_from_url(self, url: str) -> str:
        """URLから商品IDを抽出"""
        # URLから商品IDらしき部分を抽出
        match = re.search(r'/([^/]+)/?$', url.rstrip('/'))
        if match:
            return match.group(1)
        return url.split('/')[-1] or 'unknown'
    
    def _fetch_page(self, url: str) -> str:
        """Webページを取得"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as e:
            raise RakutenMonitorError(f"ページ取得エラー ({url}): {e}")
    
    def _process_url(self, url: str) -> List[Dict[str, str]]:
        """単一URLを処理して変更を検出"""
        try:
            logger.info(f"Processing URL: {url}")
            html = self._fetch_page(url)
            products = self._extract_product_info(url, html)
            
            changes = []
            for product in products:
                result = self.db.upsert_item(
                    url=product['url'],
                    product_id=product['product_id'],
                    name=product['name'],
                    price=product['price'],
                    status=product['status']
                )
                
                if result['change_type'] in ['new_item', 'restock']:
                    changes.append(result)
            
            return changes
            
        except LayoutChangeError as e:
            logger.error(f"Layout change detected: {e}")
            if self.notifier:
                self.notifier.notify_error("layout", str(e))
            raise
        except Exception as e:
            logger.error(f"URL processing failed: {e}")
            raise
    
    def run_monitoring(self) -> None:
        """監視を実行"""
        try:
            # 設定読み込み
            config = self.config_loader.load_config()
            self.notifier = DiscordNotifier(config['webhookUrl'])
            
            # 監視時間チェック
            if not self._is_monitoring_time():
                logger.info("Outside monitoring hours, exiting quietly")
                return
            
            logger.info("Starting Rakuten item monitoring")
            
            all_changes = []
            for url in config['urls']:
                try:
                    changes = self._process_url(url)
                    all_changes.extend(changes)
                except Exception as e:
                    logger.error(f"Failed to process {url}: {e}")
                    continue
            
            # 通知送信
            for change in all_changes:
                try:
                    if change['change_type'] == 'new_item':
                        self.notifier.notify_new_item(change)
                    elif change['change_type'] == 'restock':
                        self.notifier.notify_restock(change)
                except DiscordNotificationError as e:
                    logger.error(f"Failed to send notification: {e}")
            
            logger.info(f"Monitoring completed. Found {len(all_changes)} changes")
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
        except DatabaseConnectionError as e:
            logger.error(f"Database error: {e}")
            if hasattr(self, 'notifier') and self.notifier:
                self.notifier.notify_error("db", str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='楽天商品監視ツール')
    parser.add_argument('--config', default='config.json', help='設定ファイルパス')
    parser.add_argument('--cron', action='store_true', help='cron実行モード')
    parser.add_argument('--test', action='store_true', help='接続テストモード')
    
    args = parser.parse_args()
    
    try:
        monitor = RakutenMonitor(args.config)
        
        if args.test:
            # 接続テスト
            config = monitor.config_loader.load_config()
            notifier = DiscordNotifier(config['webhookUrl'])
            if notifier.test_connection():
                print("Discord接続テスト成功")
            else:
                print("Discord接続テスト失敗")
                sys.exit(1)
        else:
            # 通常の監視実行
            monitor.run_monitoring()
            
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
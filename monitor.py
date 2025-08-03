"""楽天商品監視ツール メインCLI"""
import argparse
import logging
import sys
import time
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
import re

try:
    from .config_loader import ConfigLoader
    from .item_db import ItemDB
    from .discord_notifier import DiscordNotifier
    from .prometheus_client import push_failure_metric, push_monitoring_metric, push_database_metric
    from .exceptions import (
        RakutenMonitorError, 
        LayoutChangeError, 
        DatabaseConnectionError,
        ConfigurationError,
        DiscordNotificationError,
        NetworkError,
        PrometheusError
    )
except ImportError:
    from config_loader import ConfigLoader
    from item_db import ItemDB
    from discord_notifier import DiscordNotifier
    from prometheus_client import push_failure_metric, push_monitoring_metric, push_database_metric
    from exceptions import (
        RakutenMonitorError, 
        LayoutChangeError, 
        DatabaseConnectionError,
        ConfigurationError,
        DiscordNotificationError,
        NetworkError,
        PrometheusError
    )


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RakutenMonitor:
    """楽天商品監視ツールのメインクラス"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_loader = ConfigLoader(config_path)
        self.db = None
        self.notifier = None
    
    def _test_database_connection(self) -> bool:
        """PostgreSQLデータベース接続をテスト"""
        try:
            with ItemDB() as db:
                # 簡単な接続テスト
                db.get_item('test_connection')
                logger.info("PostgreSQL接続テスト成功")
                return True
        except Exception as e:
            logger.error(f"PostgreSQL接続テスト失敗: {e}")
            return False
    
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
    
    def _extract_price_number(self, price_str: str) -> int:
        """価格文字列から数値を抽出"""
        try:
            # 数字以外を除去
            price_num = re.sub(r'[^\d]', '', price_str)
            return int(price_num) if price_num else 0
        except (ValueError, TypeError):
            return 0
    
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
        except requests.exceptions.Timeout as e:
            raise NetworkError(f"ページ取得タイムアウト: {e}", url=url, timeout=True)
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"ページ接続エラー: {e}", url=url, timeout=False)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise LayoutChangeError(f"ページが見つかりません (404): {url}")
            elif e.response.status_code >= 500:
                raise NetworkError(f"サーバーエラー ({e.response.status_code}): {e}", url=url)
            else:
                raise NetworkError(f"HTTPエラー ({e.response.status_code}): {e}", url=url)
        except requests.RequestException as e:
            raise NetworkError(f"ページ取得エラー: {e}", url=url)
    
    def _process_url(self, url: str) -> List[Dict[str, str]]:
        """単一URLを処理して変更を検出"""
        try:
            logger.info(f"Processing URL: {url}")
            html = self._fetch_page(url)
            products = self._extract_product_info(url, html)
            
            changes = []
            with ItemDB() as db:
                for product in products:
                    # PostgreSQL用にitem_codeを生成
                    item_code = f"{product['url']}_{product['product_id']}"
                    
                    # 既存アイテムの確認
                    existing_item = db.get_item(item_code)
                    
                    # アイテムを保存
                    item_dict = {
                        'item_code': item_code,
                        'title': product['name'],
                        'price': self._extract_price_number(product['price']),
                        'status': product['status']
                    }
                    db.save_item(item_dict)
                    
                    # 変更検出
                    if not existing_item:
                        if product['status'] == '在庫あり':
                            changes.append({
                                'change_type': 'new_item',
                                'name': product['name'],
                                'price': product['price'],
                                'status': product['status'],
                                'url': product['url']
                            })
                    elif existing_item['status'] == '売り切れ' and product['status'] == '在庫あり':
                        changes.append({
                            'change_type': 'restock',
                            'name': product['name'],
                            'price': product['price'],
                            'status': product['status'],
                            'url': product['url']
                        })
            
            return changes
            
        except LayoutChangeError as e:
            logger.error(f"Layout change detected: {e}")
            # Discord 警告通知
            if self.notifier:
                try:
                    self.notifier.send_warning(
                        title="ページ構造変更",
                        message="楽天市場のページ構造が変更された可能性があります。",
                        details=f"URL: {url}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send Discord warning: {discord_err}")
            
            # Prometheus メトリクス送信
            try:
                push_failure_metric("layout", str(e))
            except PrometheusError as prom_err:
                logger.error(f"Failed to push layout error metric: {prom_err}")
            
            raise
        except DatabaseConnectionError as e:
            logger.error(f"Database connection failed: {e}")
            # Discord 重大エラー通知
            if self.notifier:
                try:
                    self.notifier.send_critical(
                        title="データベース接続エラー",
                        message="PostgreSQLデータベースに接続できません。",
                        details=str(e)
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send Discord critical alert: {discord_err}")
            
            # Prometheus メトリクス送信
            try:
                push_failure_metric("db", str(e))
            except PrometheusError as prom_err:
                logger.error(f"Failed to push database error metric: {prom_err}")
            
            raise
        except NetworkError as e:
            logger.error(f"Network error: {e}")
            # Discord 警告通知
            if self.notifier:
                try:
                    self.notifier.send_warning(
                        title="ネットワークエラー",
                        message="楽天市場への接続に失敗しました。",
                        details=f"URL: {e.url or url}\nタイムアウト: {'Yes' if e.timeout else 'No'}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send Discord network warning: {discord_err}")
            
            # Prometheus メトリクス送信
            try:
                push_failure_metric("network", str(e))
            except PrometheusError as prom_err:
                logger.error(f"Failed to push network error metric: {prom_err}")
            
            raise
        except Exception as e:
            logger.error(f"URL processing failed: {e}")
            # 予期しないエラーの場合も Discord に通知
            if self.notifier:
                try:
                    self.notifier.send_critical(
                        title="予期しないエラー",
                        message="商品処理中に予期しないエラーが発生しました。",
                        details=f"URL: {url}\nエラータイプ: {type(e).__name__}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send Discord unexpected error alert: {discord_err}")
            
            # Prometheus メトリクス送信
            try:
                push_failure_metric("unexpected", str(e))
            except PrometheusError as prom_err:
                logger.error(f"Failed to push unexpected error metric: {prom_err}")
            
            raise
    
    def run_monitoring(self) -> None:
        """監視を実行"""
        start_time = time.time()
        items_processed = 0
        changes_found = 0
        
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
            urls_to_process = config['urls']
            
            for url in urls_to_process:
                try:
                    changes = self._process_url(url)
                    all_changes.extend(changes)
                    items_processed += 1
                except LayoutChangeError as e:
                    # レイアウト変更エラーは既に _process_url で処理済み
                    logger.error(f"Layout change detected for {url}: {e}")
                    continue
                except DatabaseConnectionError as e:
                    # データベースエラーは既に _process_url で処理済み
                    logger.error(f"Database error for {url}: {e}")
                    continue
                except NetworkError as e:
                    # ネットワークエラーは既に _process_url で処理済み
                    logger.error(f"Network error for {url}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing {url}: {e}")
                    continue
            
            changes_found = len(all_changes)
            
            # 通知送信
            discord_failures = 0
            for change in all_changes:
                try:
                    if change['change_type'] == 'new_item':
                        self.notifier.notify_new_item(change)
                    elif change['change_type'] == 'restock':
                        self.notifier.notify_restock(change)
                except DiscordNotificationError as e:
                    discord_failures += 1
                    logger.error(f"Failed to send notification: {e}")
                    # Discord障害をPrometheusに記録
                    try:
                        push_failure_metric("discord", str(e))
                    except PrometheusError as prom_err:
                        logger.error(f"Failed to push Discord error metric: {prom_err}")
            
            # Discord通知失敗が多い場合は警告
            if discord_failures > 0:
                logger.warning(f"Discord notification failures: {discord_failures}/{len(all_changes)}")
                if discord_failures >= len(all_changes) // 2:  # 半数以上失敗
                    try:
                        self.notifier.send_critical(
                            title="Discord通知システム障害",
                            message=f"Discord通知の送信に複数回失敗しました ({discord_failures}/{len(all_changes)})。",
                            details="Discord Webhookの設定やネットワーク接続を確認してください。"
                        )
                    except DiscordNotificationError:
                        # Discord自体が死んでる場合はログのみ
                        logger.critical("Critical: Discord notification system appears to be down")
            
            # 監視完了メトリクス送信
            duration = time.time() - start_time
            try:
                push_monitoring_metric(items_processed, changes_found, duration)
            except PrometheusError as e:
                logger.error(f"Failed to push monitoring metrics: {e}")
            
            logger.info(f"Monitoring completed. Processed {items_processed} URLs, found {changes_found} changes in {duration:.2f}s")
            
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
            print("=== PostgreSQL & Discord 接続テスト ===")
            
            # PostgreSQL接続テスト
            if monitor._test_database_connection():
                print("✅ PostgreSQL接続テスト成功")
                db_success = True
            else:
                print("❌ PostgreSQL接続テスト失敗")
                db_success = False
            
            # Discord接続テスト
            try:
                config = monitor.config_loader.load_config()
                notifier = DiscordNotifier(config['webhookUrl'])
                if notifier.test_connection():
                    print("✅ Discord接続テスト成功")
                    discord_success = True
                else:
                    print("❌ Discord接続テスト失敗")
                    discord_success = False
            except Exception as e:
                print(f"❌ Discord接続テスト失敗: {e}")
                discord_success = False
            
            # 結果サマリー
            if db_success and discord_success:
                print("\n🎉 すべての接続テストが成功しました")
                sys.exit(0)
            else:
                print("\n⚠️  一部の接続テストが失敗しました")
                sys.exit(1)
        else:
            # 通常の監視実行 (cron/対話的実行共通)
            if args.cron:
                # cronモード: ログレベルを調整
                logging.getLogger().setLevel(logging.WARNING)
                logger.info("Running in cron mode")
            
            monitor.run_monitoring()
            
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
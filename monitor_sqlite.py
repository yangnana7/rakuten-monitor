#!/usr/bin/env python3
"""楽天商品監視ツール SQLite版"""

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

try:
    from .config_loader import ConfigLoader
    from .discord_notifier import DiscordNotifier
    from .html_parser import RakutenHtmlParser, Product
    from .models import ProductStateManager, detect_changes, DiffResult
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
    from discord_notifier import DiscordNotifier
    from html_parser import RakutenHtmlParser, Product
    from models import ProductStateManager, detect_changes, DiffResult
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


class RakutenMonitorSQLite:
    """楽天商品監視ツール SQLite版"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_loader = ConfigLoader(config_path)
        self.notifier = None
        
        # SQLiteベースの新機能
        self.html_parser = RakutenHtmlParser(timeout=3, max_retries=3)
        self.state_manager = ProductStateManager(
            storage_type="sqlite", 
            storage_path="product_states.db"
        )
    
    def _is_monitoring_time(self) -> bool:
        """現在時刻が監視時間内かチェック"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        start_time = self.config_loader.start_time
        end_time = self.config_loader.end_time
        
        return start_time <= current_time <= end_time
    
    def process_url_with_diff(self, url: str) -> DiffResult:
        """
        新しいHTML parserを使用してURLを処理し、差分を検出
        
        Args:
            url: 処理するURL
            
        Returns:
            DiffResult: 検出された変更
            
        Raises:
            LayoutChangeError: HTML構造が変更された場合
            NetworkError: ネットワークエラーの場合
            DatabaseConnectionError: データベースエラーの場合
        """
        try:
            logger.info(f"Processing URL with SQLite parser: {url}")
            
            # 新しいHTML parserで商品情報を取得
            current_products = self.html_parser.parse_product_page(url)
            logger.debug(f"Found {len(current_products)} products from {url}")
            
            # 差分を検出
            diff_result = detect_changes(current_products, self.state_manager)
            
            logger.info(f"Changes detected - New: {len(diff_result.new_items)}, "
                       f"Restocked: {len(diff_result.restocked)}, "
                       f"Out of stock: {len(diff_result.out_of_stock)}, "
                       f"Price changed: {len(diff_result.price_changed)}")
            
            return diff_result
            
        except LayoutChangeError as e:
            logger.error(f"Layout change detected for {url}: {e}")
            # Discord通知
            if self.notifier:
                try:
                    self.notifier.send_critical(
                        title="HTML構造変更検出",
                        message=f"楽天ページの構造が変更された可能性があります。",
                        details=f"URL: {url}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send layout change alert: {discord_err}")
            raise
            
        except NetworkError as e:
            logger.error(f"Network error for {url}: {e}")
            # Discord通知
            if self.notifier:
                try:
                    self.notifier.send_warning(
                        title="ネットワークエラー",
                        message=f"楽天市場への接続に失敗しました。",
                        details=f"URL: {url}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send network error alert: {discord_err}")
            raise
            
        except DatabaseConnectionError as e:
            logger.error(f"Database error for {url}: {e}")
            # Discord通知
            if self.notifier:
                try:
                    self.notifier.send_critical(
                        title="データベースエラー",
                        message=f"SQLiteデータベースに接続できません。",
                        details=f"URL: {url}\nエラー: {str(e)}"
                    )
                except DiscordNotificationError as discord_err:
                    logger.error(f"Failed to send database error alert: {discord_err}")
            raise
    
    def run_monitoring(self) -> None:
        """
        SQLiteベースの監視実行
        """
        start_time = time.time()
        urls_processed = 0
        total_changes = 0
        
        try:
            # 監視時間チェック（早期return）
            if not self._is_monitoring_time():
                logger.info("Outside monitoring hours, exiting quietly")
                return
            
            # 設定読み込み
            config = self.config_loader.load_config()
            self.notifier = DiscordNotifier(config['webhookUrl'])
            
            logger.info("Starting SQLite-based Rakuten item monitoring")
            
            urls_to_process = config['urls']
            all_diff_results = []
            
            # 各URLを処理
            for url in urls_to_process:
                try:
                    diff_result = self.process_url_with_diff(url)
                    all_diff_results.append((url, diff_result))
                    urls_processed += 1
                    
                    # 変更数をカウント
                    total_changes += (len(diff_result.new_items) + 
                                    len(diff_result.restocked) + 
                                    len(diff_result.out_of_stock) + 
                                    len(diff_result.price_changed))
                    
                except LayoutChangeError as e:
                    logger.error(f"Layout change detected for {url}: {e}")
                    continue
                    
                except (NetworkError, DatabaseConnectionError) as e:
                    logger.error(f"Error processing {url}: {e}")
                    continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing {url}: {e}")
                    continue
            
            # 通知送信
            discord_failures = 0
            for url, diff_result in all_diff_results:
                try:
                    # 新商品通知
                    for product in diff_result.new_items:
                        message = (
                            f"【新商品】{product.name} が入荷しました！ "
                            f"¥{product.price:,} {product.url}"
                        )
                        self.notifier.send_notification(message)
                    
                    # 再販通知
                    for product in diff_result.restocked:
                        message = (
                            f"【再販】{product.name} の在庫が復活しました！ "
                            f"¥{product.price:,} {product.url}"
                        )
                        self.notifier.send_notification(message)
                    
                except DiscordNotificationError as e:
                    discord_failures += 1
                    logger.error(f"Failed to send notification for {url}: {e}")
            
            # Discord通知失敗が多い場合は警告
            if discord_failures > 0:
                logger.warning(f"Discord notification failures: {discord_failures}")
            
            duration = time.time() - start_time
            logger.info(f"SQLite monitoring completed. Processed {urls_processed} URLs, "
                       f"found {total_changes} total changes in {duration:.2f}s")
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
            raise
    
    def test_connections(self) -> bool:
        """接続テスト"""
        print("=== SQLite版 接続テスト ===")
        
        # SQLite データベーステスト
        try:
            # テスト商品を作成してSQLiteに保存・読み込み
            test_product = Product(
                id="test_sqlite_123",
                name="SQLiteテスト商品",
                price=1000,
                url="https://example.com/test",
                in_stock=True
            )
            
            # SQLiteに保存
            current_products = [test_product]
            diff_result = detect_changes(current_products, self.state_manager)
            
            # データが正しく保存されたか確認
            all_states = self.state_manager.get_all_product_states()
            
            if any(state.id == "test_sqlite_123" for state in all_states):
                print("✅ SQLite データベーステスト成功")
                sqlite_success = True
            else:
                print("❌ SQLite データベーステスト失敗")
                sqlite_success = False
                
        except Exception as e:
            print(f"❌ SQLite データベーステスト失敗: {e}")
            sqlite_success = False
        
        # Discord 接続テスト
        try:
            config = self.config_loader.load_config()
            notifier = DiscordNotifier(config['webhookUrl'])
            if notifier.send_info(
                title="SQLite版接続テスト",
                message="SQLite版楽天監視システムの接続テストが正常に完了しました。",
                details="SQLiteデータベースを使用した新しい監視システムが正常に動作しています。"
            ):
                print("✅ Discord接続テスト成功")
                discord_success = True
            else:
                print("❌ Discord接続テスト失敗")
                discord_success = False
        except Exception as e:
            print(f"❌ Discord接続テスト失敗: {e}")
            discord_success = False
        
        # 結果サマリー
        if sqlite_success and discord_success:
            print("\n🎉 すべての接続テストが成功しました")
            return True
        else:
            print("\n⚠️  一部の接続テストが失敗しました")
            return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='楽天商品監視ツール SQLite版')
    parser.add_argument('--config', default='config.json', help='設定ファイルパス')
    parser.add_argument('--test', action='store_true', help='接続テストモード')
    parser.add_argument('--once', action='store_true', help='1回だけ実行')
    parser.add_argument('--debug', action='store_true', help='デバッグモード')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        monitor = RakutenMonitorSQLite(args.config)
        
        if args.test:
            success = monitor.test_connections()
            sys.exit(0 if success else 1)
        else:
            monitor.run_monitoring()
            
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
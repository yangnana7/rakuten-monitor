#!/usr/bin/env python
import argparse
import requests
import sys
import logging
from typing import Optional
from dotenv import load_dotenv
from rakuten.rakuten_parser import parse_item_info, reset_known_items
from rakuten.item_db import ItemDB
from rakuten.discord_client import DiscordClient
from rakuten.error_handler import alert_on_exception
from rakuten.utils.notifier import send_notification
import settings

load_dotenv()

log = logging.getLogger(__name__)

# Verify required environment variables on import
try:
    WEBHOOK_URL = settings.get_webhook_url()
    ALERT_WEBHOOK_URL = settings.get_alert_webhook_url()
    LIST_URL = settings.get_list_url()
    DATABASE_URL = settings.get_database_url()
except SystemExit:
    # If running in test environment, allow graceful handling
    if "pytest" not in sys.modules:
        raise

# Create Discord client for error alerts
_alert_client = DiscordClient(
    webhook_url=ALERT_WEBHOOK_URL,
    timeout=5.0,
)


def run_monitor_once(url: Optional[str] = None) -> int:
    """
    1回分の監視を実行し、通知した件数を返す。
    例外は握りつぶさず呼び出し元へ伝播。

    Args:
        url (str, optional): 監視対象URL。Noneの場合は環境変数から取得

    Returns:
        int: 通知した件数

    Raises:
        Exception: ネットワークエラーやその他の例外
    """
    notification_count = 0

    try:
        # URLの決定
        if url is None:
            url = LIST_URL

        # データベース接続
        db_path = DATABASE_URL
        if db_path.startswith("sqlite:///"):
            db_path = db_path[10:]  # Remove sqlite:/// prefix
        db = ItemDB(db_path)

        # パーサー状態リセット
        reset_known_items()

        # HTML取得
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # HTML解析（直接全体のHTMLを使用）
        # 各商品リンクを直接解析
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")
        product_links = soup.select("a.category_itemnamelink")

        for link in product_links:
            try:
                # 商品周辺のHTMLを抽出
                parent = (
                    link.find_parent("tr")
                    or link.find_parent("div")
                    or link.find_parent()
                )
                if parent:
                    item_html = str(parent)
                else:
                    item_html = str(link.find_parent())

                # 商品情報解析
                item_info = parse_item_info(item_html)

                if not item_info or not item_info.get("item_code"):
                    continue

                item_code = item_info["item_code"]
                status = item_info["status"]

                # データベース状態確認と更新
                if status == "NEW":
                    if not db.item_exists(item_code):
                        # 新商品として保存
                        db.save_item(
                            {
                                "item_code": item_code,
                                "title": item_info["title"],
                                "status": "NEW",
                            }
                        )
                        # Discord通知
                        if send_notification(item_info):
                            notification_count += 1

                elif status == "RESALE":
                    if db.item_exists(item_code):
                        # 既存商品の再販として更新
                        db.update_item_status(item_code, "RESALE")
                    else:
                        # 新商品として保存（再販マーカー付き）
                        db.save_item(
                            {
                                "item_code": item_code,
                                "title": item_info["title"],
                                "status": "RESALE",
                            }
                        )

                    # Discord通知
                    if send_notification(item_info):
                        notification_count += 1

                # UNCHANGEDの場合は通知しない

            except Exception as e:
                # 個別商品の処理エラーは継続
                print(f"Warning: Failed to process item: {e}")
                continue

        return notification_count

    except Exception as e:
        # ネットワークエラーやその他重大なエラーの場合はアラート送信
        try:
            alert_item = {
                "item_code": "SYSTEM_ERROR",
                "title": f"監視システムエラー: {str(e)}",
                "status": "ERROR",
            }
            send_notification(alert_item)
        except Exception:  # noqa: E722
            # アラート送信も失敗した場合は諦める
            pass

        # 元の例外を再発生
        raise e


def run_monitor_loop(interval: float, *, max_runs: int = None) -> int:
    """
    指定間隔でrun_monitor_onceを繰り返し実行。

    Args:
        interval (float): 実行間隔（秒）
        max_runs (int, optional): 最大実行回数。Noneなら無限実行

    Returns:
        int: 合計通知件数
    """
    import time

    total_notifications = 0
    runs = 0

    while True:
        notification_count = run_once()
        total_notifications += notification_count
        runs += 1

        if max_runs is not None and runs >= max_runs:
            break

        time.sleep(interval)

    return total_notifications


def send_test_webhook():
    """テスト用のWebhook送信"""
    dummy_item = {
        "item_code": "TEST_ITEM_001",
        "title": "テスト商品 - Webhook動作確認",
        "status": "NEW",
        "url": "https://example.com/test-item",
    }
    if send_notification(dummy_item):
        print("Webhook test successful")
    else:
        print("Webhook test failed")


def parse_args():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(description="Rakuten monitor & notifier")
    parser.add_argument(
        "--test-webhook", action="store_true", help="Send test embed then exit"
    )
    parser.add_argument(
        "--once", action="store_true", help="Run one monitoring cycle then exit"
    )
    parser.add_argument(
        "--cron", action="store_true", help="Run infinite loop (default)"
    )
    return parser.parse_args()


@alert_on_exception(_alert_client, "#monitor-alerts")
def main():
    """メイン関数"""
    args = parse_args()
    if args.test_webhook:
        send_test_webhook()
    elif args.once:
        run_monitor_once()
    else:  # default or --cron
        run_monitor_loop(interval=600)


# Backward compatibility aliases for tests
run_once = run_monitor_once
run_loop = run_monitor_loop


if __name__ == "__main__":
    main()

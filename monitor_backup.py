#!/usr/bin/env python3
"""
楽天商品監視システム - DB連携付きメインモニター
Phase 2: データベース設計完成版
"""

import json
import time
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import List, Dict, Any
from logging.handlers import RotatingFileHandler

from models import SessionLocal, Item, Change, Run, ChangeType, create_tables
from fetch_items import parse_list, LIST_URL
from diff_items import detect_changes
from discord_notifier import DiscordNotifier
from metrics import (
    metrics_server,
    run_duration_seconds,
    record_items_fetched,
    record_change_detected,
    record_run_success,
    record_run_failure,
    record_discord_notification,
    record_database_operation,
    record_upsert_operation,
)
from redis_watchdog import redis_watchdog

# ログ設定（RotatingFileHandler使用）
logger = logging.getLogger("rakuten_monitor")
logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))

# RotatingFileHandler設定
log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

file_handler = RotatingFileHandler(
    filename="rakuten_monitor.log",
    maxBytes=log_max_bytes,
    backupCount=log_backup_count,
    encoding="utf-8",
)
console_handler = logging.StreamHandler()

# フォーマッター設定
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Discord notifier for alerts (グローバルで初期化)
alert_notifier = DiscordNotifier()


def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """未捕捉例外をDiscord #alertsに通知"""
    if issubclass(exc_type, KeyboardInterrupt):
        # KeyboardInterruptは通常の終了なので通知しない
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # トレースバック情報を取得
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    error_details = "".join(tb_lines)

    # ログに記録
    logger.critical(
        "Unhandled exception occurred", exc_info=(exc_type, exc_value, exc_traceback)
    )

    # Discord alerts に通知
    try:
        alert_notifier.notify_error(
            title="Unhandled Exception",
            description=f"**{exc_type.__name__}**: {str(exc_value)[:500]}",
            error_details=error_details,
        )
    except Exception as e:
        # 通知自体でエラーが起きた場合はログに記録のみ
        logger.error(f"Failed to send exception alert to Discord: {e}")

    # デフォルトの例外ハンドラも呼び出し
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


# 未捕捉例外ハンドラを設定
sys.excepthook = handle_unhandled_exception


class RakutenMonitor:
    def __init__(self):
        self.db = SessionLocal()
        create_tables()  # テーブルが存在しない場合は作成
        self.discord_notifier = DiscordNotifier()

        # Prometheusメトリクスサーバーを開始
        try:
            metrics_server.start_server()
        except Exception as e:
            logger.warning(f"Failed to start metrics server: {e}")

        # Redis Watchdog開始
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.watchdog_task = loop.create_task(redis_watchdog.start_watchdog())
            logger.info("Redis Watchdog started")
        except Exception as e:
            logger.warning(f"Failed to start Redis Watchdog: {e}")
            self.watchdog_task = None

    def close(self):
        """データベース接続を閉じる"""
        self.db.close()

        # Redis Watchdog停止
        if hasattr(self, "watchdog_task") and self.watchdog_task:
            import asyncio

            loop = asyncio.get_event_loop()
            loop.run_until_complete(redis_watchdog.stop_watchdog())
            self.watchdog_task.cancel()

    def save_run_metadata(self, fetched_at: datetime, snapshot_data: Dict) -> int:
        """実行メタデータを保存"""
        run = Run(
            fetched_at=fetched_at,
            snapshot=json.dumps(snapshot_data, ensure_ascii=False),
        )
        self.db.add(run)
        self.db.commit()
        logger.info(f"Run metadata saved: {run.id}")
        return run.id

    def upsert_items(self, items: List[Dict]) -> None:
        """商品データをBulk Upsert（存在すれば更新、なければ挿入）"""
        if not items:
            return

        now = datetime.now()
        start_time = time.time()

        try:
            # データベースタイプを判定
            database_type = (
                "postgresql" if "postgresql" in str(self.db.bind.url) else "sqlite"
            )

            # PostgreSQLとSQLiteで異なるupsert処理
            if database_type == "postgresql":
                self._bulk_upsert_postgresql(items, now)
            else:
                self._bulk_upsert_sqlite(items, now)

            # メトリクス記録
            duration = time.time() - start_time
            record_database_operation("bulk_upsert", True)
            record_upsert_operation(database_type, len(items), duration)

            logger.info(
                f"Bulk upserted {len(items)} items in {duration:.3f}s ({database_type})"
            )

        except Exception as e:
            self.db.rollback()
            duration = time.time() - start_time
            database_type = (
                "postgresql" if "postgresql" in str(self.db.bind.url) else "sqlite"
            )
            record_database_operation("bulk_upsert", False)
            logger.error(f"Failed to bulk upsert items: {e}")
            raise

    def _bulk_upsert_postgresql(self, items: List[Dict], now: datetime) -> None:
        """PostgreSQL用のbulk upsert"""
        from sqlalchemy.dialects.postgresql import insert

        # データ準備
        item_data = []
        for item in items:
            item_data.append(
                {
                    "code": item["code"],
                    "title": item["title"],
                    "price": item["price"],
                    "in_stock": item["in_stock"],
                    "first_seen": now,
                    "last_seen": now,
                }
            )

        # ON CONFLICT DO UPDATE
        stmt = insert(Item).values(item_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code"],
            set_={
                "title": stmt.excluded.title,
                "price": stmt.excluded.price,
                "in_stock": stmt.excluded.in_stock,
                "last_seen": stmt.excluded.last_seen,
            },
        )

        self.db.execute(stmt)
        self.db.commit()

    def _bulk_upsert_sqlite(self, items: List[Dict], now: datetime) -> None:
        """SQLite用のbulk upsert（INSERT OR REPLACE使用）"""
        from sqlalchemy import text

        # SQLiteのINSERT OR REPLACEを使用
        sql = """
        INSERT OR REPLACE INTO items (code, title, price, in_stock, first_seen, last_seen)
        VALUES (:code, :title, :price, :in_stock,
                COALESCE((SELECT first_seen FROM items WHERE code = :code), :first_seen),
                :last_seen)
        """

        # データ準備
        item_data = []
        for item in items:
            item_data.append(
                {
                    "code": item["code"],
                    "title": item["title"],
                    "price": item["price"],
                    "in_stock": item["in_stock"],
                    "first_seen": now,
                    "last_seen": now,
                }
            )

        self.db.execute(text(sql), item_data)
        self.db.commit()

    def save_changes(self, changes: List[Dict]) -> None:
        """変更イベントをデータベースに保存"""
        for change_data in changes:
            change_type = ChangeType(change_data["type"])

            # payloadの準備
            payload = {}
            if change_type == ChangeType.TITLE_UPDATE:
                payload = {
                    "old_title": change_data.get("old_title"),
                    "new_title": change_data.get("new_title"),
                }
            elif change_type == ChangeType.PRICE_UPDATE:
                payload = {
                    "old_price": change_data.get("old_price"),
                    "new_price": change_data.get("new_price"),
                }

            change = Change(
                code=change_data["code"],
                type=change_type,
                payload=json.dumps(payload) if payload else None,
            )
            self.db.add(change)
            logger.info(
                f"Change saved: {change_data['type']} for {change_data['code']}"
            )

        if changes:
            self.db.commit()

    def get_previous_snapshot(self) -> Dict[str, Any]:
        """前回のスナップショットを取得"""
        latest_run = self.db.query(Run).order_by(Run.fetched_at.desc()).first()

        if latest_run and latest_run.snapshot:
            return json.loads(latest_run.snapshot)

        return {"fetched_at": 0, "items": []}

    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """監視サイクルを1回実行"""
        logger.info("Starting monitoring cycle")
        fetched_at = datetime.now()

        # Prometheusメトリクスでタイマー開始
        with run_duration_seconds.time():
            try:
                # 商品データを取得
                current_items = parse_list(LIST_URL)
                if not current_items:
                    logger.warning("No items fetched")
                    record_run_failure()
                    return {"success": False, "error": "No items fetched"}

                # メトリクス記録
                record_items_fetched(len(current_items))

                # 現在のスナップショット
                current_snapshot = {
                    "fetched_at": int(fetched_at.timestamp()),
                    "items": current_items,
                }

                # 前回のスナップショットを取得
                previous_snapshot = self.get_previous_snapshot()

                # 変更を検出
                changes = []
                if previous_snapshot["items"]:
                    changes = detect_changes(current_snapshot, previous_snapshot)
                    logger.info(f"Detected {len(changes)} changes")

                    # 変更タイプごとにメトリクス記録
                    for change in changes:
                        record_change_detected(change["type"])
                else:
                    logger.info("No previous snapshot found, skipping change detection")

                # データベースに保存
                run_id = self.save_run_metadata(fetched_at, current_snapshot)
                self.upsert_items(current_items)

                if changes:
                    self.save_changes(changes)
                    # Discord通知を送信
                    notification_success = self.discord_notifier.send_notification(
                        changes
                    )
                    record_discord_notification("change", notification_success)

                result = {
                    "success": True,
                    "run_id": run_id,
                    "items_count": len(current_items),
                    "changes_count": len(changes),
                    "changes": changes,
                }

                # 成功をメトリクスに記録
                record_run_success()

                logger.info(
                    f"Monitoring cycle completed: {len(current_items)} items, {len(changes)} changes"
                )
                return result

            except Exception as e:
                logger.error(f"Monitoring cycle failed: {e}")
                record_run_failure()

                # エラー通知を送信
                try:
                    self.discord_notifier.notify_error(
                        title="Monitoring Cycle Failed",
                        description=f"Monitoring cycle encountered an error: {str(e)[:500]}",
                        error_details=str(e),
                    )
                    record_discord_notification("error", True)
                except Exception as notify_error:
                    logger.error(f"Failed to send error notification: {notify_error}")
                    record_discord_notification("error", False)

                return {"success": False, "error": str(e)}


def main():
    """メイン実行関数"""
    monitor = RakutenMonitor()

    try:
        result = monitor.run_monitoring_cycle()

        if result["success"]:
            print("OK Monitoring completed successfully")
            print(f"  Items: {result['items_count']}")
            print(f"  Changes: {result['changes_count']}")

            if result["changes"]:
                print("\nDetected changes:")
                for change in result["changes"]:
                    print(
                        f"  - {change['type']}: {change.get('title', change['code'])}"
                    )
        else:
            print(f"NG Monitoring failed: {result.get('error', 'Unknown error')}")
            return 1

    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        monitor.close()

    return 0


if __name__ == "__main__":
    exit(main())

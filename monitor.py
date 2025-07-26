#!/usr/bin/env python3
"""
楽天商品監視システム - DB連携付きメインモニター
Phase 2: データベース設計完成版
"""

import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import SessionLocal, Item, Change, Run, ChangeType, create_tables
from fetch_items import parse_list, LIST_URL
from diff_items import detect_changes
from discord_notifier import DiscordNotifier

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RakutenMonitor:
    def __init__(self):
        self.db = SessionLocal()
        create_tables()  # テーブルが存在しない場合は作成
        self.discord_notifier = DiscordNotifier()
    
    def close(self):
        """データベース接続を閉じる"""
        self.db.close()
    
    def save_run_metadata(self, fetched_at: datetime, snapshot_data: Dict) -> int:
        """実行メタデータを保存"""
        run = Run(
            fetched_at=fetched_at,
            snapshot=json.dumps(snapshot_data, ensure_ascii=False)
        )
        self.db.add(run)
        self.db.commit()
        logger.info(f"Run metadata saved: {run.id}")
        return run.id
    
    def upsert_items(self, items: List[Dict]) -> None:
        """商品データをUpsert（存在すれば更新、なければ挿入）"""
        now = datetime.now()
        
        for item_data in items:
            existing_item = self.db.query(Item).filter(
                Item.code == item_data['code']
            ).first()
            
            if existing_item:
                # 既存商品の更新
                existing_item.title = item_data['title']
                existing_item.price = item_data['price']
                existing_item.in_stock = item_data['in_stock']
                existing_item.last_seen = now
                logger.debug(f"Updated item: {item_data['code']}")
            else:
                # 新商品の追加
                new_item = Item(
                    code=item_data['code'],
                    title=item_data['title'],
                    price=item_data['price'],
                    in_stock=item_data['in_stock'],
                    first_seen=now,
                    last_seen=now
                )
                self.db.add(new_item)
                logger.info(f"New item added: {item_data['code']}")
        
        self.db.commit()
    
    def save_changes(self, changes: List[Dict]) -> None:
        """変更イベントをデータベースに保存"""
        for change_data in changes:
            change_type = ChangeType(change_data['type'])
            
            # payloadの準備
            payload = {}
            if change_type == ChangeType.TITLE_UPDATE:
                payload = {
                    'old_title': change_data.get('old_title'),
                    'new_title': change_data.get('new_title')
                }
            elif change_type == ChangeType.PRICE_UPDATE:
                payload = {
                    'old_price': change_data.get('old_price'),
                    'new_price': change_data.get('new_price')
                }
            
            change = Change(
                code=change_data['code'],
                type=change_type,
                payload=json.dumps(payload) if payload else None
            )
            self.db.add(change)
            logger.info(f"Change saved: {change_data['type']} for {change_data['code']}")
        
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
        
        try:
            # 商品データを取得
            current_items = parse_list(LIST_URL)
            if not current_items:
                logger.warning("No items fetched")
                return {"success": False, "error": "No items fetched"}
            
            # 現在のスナップショット
            current_snapshot = {
                "fetched_at": int(fetched_at.timestamp()),
                "items": current_items
            }
            
            # 前回のスナップショットを取得
            previous_snapshot = self.get_previous_snapshot()
            
            # 変更を検出
            changes = []
            if previous_snapshot["items"]:
                changes = detect_changes(current_snapshot, previous_snapshot)
                logger.info(f"Detected {len(changes)} changes")
            else:
                logger.info("No previous snapshot found, skipping change detection")
            
            # データベースに保存
            run_id = self.save_run_metadata(fetched_at, current_snapshot)
            self.upsert_items(current_items)
            
            if changes:
                self.save_changes(changes)
                # Discord通知を送信
                self.discord_notifier.send_notification(changes)
            
            result = {
                "success": True,
                "run_id": run_id,
                "items_count": len(current_items),
                "changes_count": len(changes),
                "changes": changes
            }
            
            logger.info(f"Monitoring cycle completed: {len(current_items)} items, {len(changes)} changes")
            return result
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            return {"success": False, "error": str(e)}

def main():
    """メイン実行関数"""
    monitor = RakutenMonitor()
    
    try:
        result = monitor.run_monitoring_cycle()
        
        if result["success"]:
            print(f"✓ Monitoring completed successfully")
            print(f"  Items: {result['items_count']}")
            print(f"  Changes: {result['changes_count']}")
            
            if result["changes"]:
                print("\nDetected changes:")
                for change in result["changes"]:
                    print(f"  - {change['type']}: {change.get('title', change['code'])}")
        else:
            print(f"✗ Monitoring failed: {result.get('error', 'Unknown error')}")
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
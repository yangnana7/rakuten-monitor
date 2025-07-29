#!/usr/bin/env python3
"""
最新スナップショットと直前スナップショットを比較し、
NEW / RESTOCK / TITLE_UPDATE / SOLDOUT を抽出して JSON で返す
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any


def get_snapshots(snapshots_dir: Path) -> List[Path]:
    """スナップショットファイルを取得（作成時刻順でソート）"""
    files = list(snapshots_dir.glob("*.json"))
    return sorted(files, key=lambda p: p.stat().st_mtime)


def load_snapshot(file_path: Path) -> Dict[str, Any]:
    """スナップショットファイルを読み込み"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_changes(latest: Dict, previous: Dict) -> List[Dict]:
    """変更を検出してイベントリストを返す"""
    now_items = {i["code"]: i for i in latest["items"]}
    old_items = {i["code"]: i for i in previous["items"]}

    events = []

    # 新商品・再入荷・タイトル変更の検知
    for code, item in now_items.items():
        if code not in old_items:
            events.append({"type": "NEW", **item})
        else:
            old = old_items[code]
            # 再入荷検知
            if (not old["in_stock"]) and item["in_stock"]:
                events.append({"type": "RESTOCK", **item})
            # タイトル変更検知
            if old["title"] != item["title"]:
                events.append(
                    {
                        "type": "TITLE_UPDATE",
                        "code": code,
                        "title": item["title"],
                        "old_title": old["title"],
                        "new_title": item["title"],
                        "url": item["url"],
                    }
                )
            # 価格変更検知
            if old["price"] != item["price"]:
                events.append(
                    {
                        "type": "PRICE_UPDATE",
                        "code": code,
                        "title": item["title"],
                        "old_price": old["price"],
                        "new_price": item["price"],
                        "price": item["price"],
                        "url": item["url"],
                        "in_stock": item["in_stock"],
                    }
                )

    # 売り切れ検知
    for code, old in old_items.items():
        if code in now_items:
            item = now_items[code]
            if old["in_stock"] and not item["in_stock"]:
                events.append({"type": "SOLDOUT", **item})

    return events


def main():
    parser = argparse.ArgumentParser(description="楽天商品監視 差分検知ツール")
    parser.add_argument(
        "--snapshots-dir",
        type=str,
        default="snapshots",
        help="スナップショットディレクトリ (default: snapshots)",
    )
    parser.add_argument("--latest", action="store_true", help="最新スナップショットのみ表示")

    args = parser.parse_args()

    snapshots_dir = Path(args.snapshots_dir)

    if not snapshots_dir.exists():
        sys.exit(f"Snapshots directory not found: {snapshots_dir}")

    files = get_snapshots(snapshots_dir)

    if args.latest:
        if not files:
            sys.exit("No snapshots found")
        latest = load_snapshot(files[-1])
        print(json.dumps(latest, ensure_ascii=False, indent=2))
        return

    if len(files) < 2:
        sys.exit("Need ≥2 snapshots for comparison")

    latest = load_snapshot(files[-1])
    previous = load_snapshot(files[-2])

    events = detect_changes(latest, previous)

    print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

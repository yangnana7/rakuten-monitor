#!/usr/bin/env python3
"""
Rakuten Entamestore - 子役カウンター監視 PoC
USAGE: python fetch_items.py > snapshots/$(date +%s).json
"""
import re
import json
import sys
import time
import requests
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

# 環境変数を読み込み
load_dotenv()

LIST_URL = os.getenv('LIST_URL', "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4")
UA = os.getenv('USER_AGENT', "Mozilla/5.0 (X11; Linux x86_64) Gecko")

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fetch_items.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_session_with_retry() -> requests.Session:
    """リトライ機能付きのHTTPセッションを作成"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def parse_list(url: str) -> List[Dict]:
    """商品一覧ページをパースして商品データを返す"""
    session = create_session_with_retry()
    
    try:
        logger.info(f"Fetching URL: {url}")
        response = session.get(url, headers={"User-Agent": UA}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        rows = []
        # 楽天の商品リンクを直接取得
        product_links = soup.select("a.category_itemnamelink")
        logger.info(f"Found {len(product_links)} product links")
        
        for a in product_links:
            try:
                href = urljoin(url, a["href"])
                code = urlparse(href).path.rstrip("/").split("/")[-1]
                title = a.get_text(strip=True)
                
                # 価格を取得（複数の方法で試行）
                price = None
                # 方法1: 親要素から価格を探す
                parent = a.find_parent()
                if parent:
                    price_el = parent.find("span", class_="category_itemprice")
                else:
                    price_el = None
                
                if not price_el:
                    # 方法2: 同じtr内の価格要素を探す
                    tr_parent = a.find_parent('tr')
                    if tr_parent:
                        price_el = tr_parent.find("span", class_="category_itemprice")
                
                if price_el:
                    price_text = price_el.get_text()
                    price_match = re.search(r'([\d,]+)', price_text)
                    if price_match:
                        price = int(price_match.group(1).replace(',', ''))
                
                # 在庫状況（売り切れ表示があるかチェック）
                parent = a.find_parent('td') or a.find_parent()
                sold = bool(parent and parent.select_one(".soldOut, .soldout, .iconSoldout"))
                
                rows.append({
                    "code": code,
                    "title": title,
                    "price": price,
                    "in_stock": not sold,
                    "url": href,
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse product: {e}")
                continue
                
        logger.info(f"Successfully parsed {len(rows)} products")
        return rows
        
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Parsing failed: {e}")
        return []

if __name__ == "__main__":
    data = parse_list(LIST_URL)
    print(json.dumps({
        "fetched_at": int(time.time()),
        "items": data,
    }, ensure_ascii=False, indent=2))
#!/usr/bin/env python3
"""
Rakuten Entamestore - 子役カウンター監視 PoC
USAGE: python fetch_items.py > snapshots/$(date +%s).json
"""

import re
import json
import time
import requests
import logging
import cloudscraper
import asyncio
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not available - falling back to cloudscraper only")

# 環境変数を読み込み
load_dotenv()

LIST_URL = os.getenv("LIST_URL", "https://item.rakuten.co.jp/auc-p-entamestore/c/0000000174/?s=4")
UA = os.getenv("USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64) Gecko")

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("fetch_items.log"), logging.StreamHandler()],
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


def fetch_with_cloudscraper(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """Cloudscraperを使用してページを取得"""
    start_time = time.time()
    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "linux", "desktop": True}
        )
        logger.info(f"Fetching with cloudscraper: {url}")
        response = scraper.get(url, timeout=timeout)
        response.raise_for_status()

        duration = time.time() - start_time
        # メトリクス記録（成功時は後で統合記録）
        return response
    except cloudscraper.exceptions.CloudflareChallengeError as e:
        duration = time.time() - start_time
        try:
            from metrics import record_fetch_attempt

            record_fetch_attempt("cloudscraper", False, duration)
        except ImportError:
            pass
        logger.warning(f"Cloudflare challenge detected: {e}")
        return None
    except Exception as e:
        duration = time.time() - start_time
        try:
            from metrics import record_fetch_attempt

            record_fetch_attempt("cloudscraper", False, duration)
        except ImportError:
            pass
        logger.error(f"Cloudscraper failed: {e}")
        return None


async def fetch_with_playwright(url: str, timeout: int = 30000) -> Optional[str]:
    """Playwrightを使用してページを取得（Cloudflareバイパス）"""
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available")
        return None

    try:
        logger.info(f"Fetching with playwright: {url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                user_agent=UA, viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()

            # タイムアウト設定
            page.set_default_timeout(timeout)

            # ページに移動
            await page.goto(url, wait_until="domcontentloaded")

            # Cloudflareチャレンジの待機
            try:
                await page.wait_for_selector("a.category_itemnamelink", timeout=10000)
            except Exception:
                # 商品リンクが見つからない場合、少し待つ
                await page.wait_for_timeout(3000)

            content = await page.content()
            await browser.close()
            return content

    except Exception as e:
        logger.error(f"Playwright failed: {e}")
        return None


def fetch_with_retry(url: str) -> Optional[requests.Response]:
    """複数の方法でページを取得（Cloudflare対策）"""

    # 方法1: 通常のrequests
    start_time = time.time()
    try:
        session = create_session_with_retry()
        logger.info(f"Fetching with requests: {url}")
        response = session.get(url, headers={"User-Agent": UA}, timeout=30)
        if response.status_code == 200:
            duration = time.time() - start_time
            try:
                from metrics import record_fetch_attempt

                record_fetch_attempt("requests", True, duration)
            except ImportError:
                pass
            return response
    except requests.RequestException as e:
        duration = time.time() - start_time
        try:
            from metrics import record_fetch_attempt

            record_fetch_attempt("requests", False, duration)
        except ImportError:
            pass
        logger.warning(f"Standard requests failed: {e}")

    # 方法2: Cloudscraper
    start_time = time.time()
    response = fetch_with_cloudscraper(url)
    if response:
        duration = time.time() - start_time
        try:
            from metrics import record_fetch_attempt

            record_fetch_attempt("cloudscraper", True, duration)
        except ImportError:
            pass
        return response

    # 方法3: Playwright（非同期なので別途処理）
    start_time = time.time()
    logger.info("Trying Playwright fallback...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        content = loop.run_until_complete(fetch_with_playwright(url))
        if content:
            duration = time.time() - start_time
            try:
                from metrics import record_fetch_attempt

                record_fetch_attempt("playwright", True, duration)
            except ImportError:
                pass

            # 疑似レスポンスオブジェクトを作成
            class MockResponse:
                def __init__(self, text, status_code=200):
                    self.text = text
                    self.status_code = status_code

                def raise_for_status(self):
                    if self.status_code >= 400:
                        raise requests.HTTPError(f"HTTP {self.status_code}")

            return MockResponse(content)
    except Exception as e:
        duration = time.time() - start_time
        try:
            from metrics import record_fetch_attempt

            record_fetch_attempt("playwright", False, duration)
        except ImportError:
            pass
        logger.error(f"Playwright fallback failed: {e}")
    finally:
        loop.close()

    logger.error("All fetch methods failed")
    return None


def parse_list(url: str) -> List[Dict]:
    """商品一覧ページをパースして商品データを返す"""
    try:
        logger.info(f"Fetching URL: {url}")
        response = fetch_with_retry(url)

        if not response:
            logger.error("Failed to fetch page with all methods")
            return []

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
                    tr_parent = a.find_parent("tr")
                    if tr_parent:
                        price_el = tr_parent.find("span", class_="category_itemprice")

                if price_el:
                    price_text = price_el.get_text()
                    price_match = re.search(r"([\d,]+)", price_text)
                    if price_match:
                        price = int(price_match.group(1).replace(",", ""))

                # 在庫状況（売り切れ表示があるかチェック）
                parent = a.find_parent("td") or a.find_parent()
                sold = bool(parent and parent.select_one(".soldOut, .soldout, .iconSoldout"))

                rows.append(
                    {
                        "code": code,
                        "title": title,
                        "price": price,
                        "in_stock": not sold,
                        "url": href,
                    }
                )

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
    print(
        json.dumps(
            {
                "fetched_at": int(time.time()),
                "items": data,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

#!/usr/bin/env python3
"""HTML デバッグ用スクリプト"""

import requests
from bs4 import BeautifulSoup

def debug_rakuten_page(url):
    """楽天ページのHTML構造をデバッグ"""
    print(f"Analyzing URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # エンコーディングを適切に設定
        if 'charset' in response.headers.get('content-type', ''):
            response.encoding = response.apparent_encoding
        else:
            response.encoding = 'euc-jp'  # 楽天の古いページ
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"Title: {soup.title.string if soup.title else 'No title'}")
        print(f"Response encoding: {response.encoding}")
        print(f"Content length: {len(response.text)}")
        
        # カテゴリページの判定要素をチェック
        print("\n=== Category Page Indicators ===")
        
        category_selectors = [
            '.searchresultitem',
            '.item-grid',
            '[data-automation-id="searchResultItem"]',
            '.product-item',
            '.item-tile',
            '.item',
            '.product',
            'div[class*="item"]',
            'div[class*="product"]',
            'li[class*="item"]',
        ]
        
        for selector in category_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"✓ Found {len(elements)} elements with selector: {selector}")
                if len(elements) <= 5:  # 少数の場合は内容も表示
                    for i, elem in enumerate(elements[:3]):
                        print(f"  [{i}]: {str(elem)[:400]}...")
                        
                        # 商品リンクを探す
                        links = elem.find_all('a', href=True)
                        if links:
                            print(f"    Links found: {len(links)}")
                            for j, link in enumerate(links[:2]):
                                href = link.get('href', '')
                                text = link.get_text(strip=True)[:50]
                                print(f"      Link[{j}]: {href} -> '{text}'")
                        
                        # 価格情報を探す
                        price_texts = []
                        for text in elem.stripped_strings:
                            if '円' in text or '¥' in text or text.isdigit():
                                price_texts.append(text)
                        if price_texts:
                            print(f"    Price texts: {price_texts[:3]}")
                        
                        print()
            else:
                print(f"✗ No elements found for selector: {selector}")
        
        # 単一商品ページの判定要素もチェック
        print("\n=== Single Product Page Indicators ===")
        
        single_product_selectors = [
            'h1.item_name',
            'h1[data-automation-id="itemName"]',
            'h1.product-title',
            '.item-name h1',
            'h1',
            '.item_price',
            '[data-automation-id="itemPrice"]',
        ]
        
        for selector in single_product_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"✓ Single product selector '{selector}': {elements[0].get_text(strip=True)[:100]}")
            else:
                print(f"✗ No elements found for single product selector: {selector}")
        
        # URL構造もチェック
        print(f"\n=== URL Analysis ===")
        print(f"URL contains '/c/': {'/c/' in url}")
        print(f"URL contains '?s=': {'?s=' in url}")
        print(f"URL contains '/item.rakuten.co.jp/': {'/item.rakuten.co.jp/' in url}")
        
        return soup
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://search.rakuten.co.jp/search/mall/nintendo+switch/"
    debug_rakuten_page(url)
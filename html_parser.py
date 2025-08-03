"""楽天商品ページのHTMLパーサー"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .exceptions import LayoutChangeError, NetworkError
except ImportError:
    from exceptions import LayoutChangeError, NetworkError

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """商品情報を表すデータクラス"""
    id: str        # item_code or SKU
    name: str      # 商品名
    price: int     # 価格（円）
    url: str       # 商品URL
    in_stock: bool # 在庫状況


class RakutenHtmlParser:
    """楽天商品ページのHTMLパーサー"""
    
    def __init__(self, timeout: int = 3, max_retries: int = 3):
        """
        Args:
            timeout: HTTPリクエストタイムアウト（秒）
            max_retries: 最大リトライ回数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # User-Agentを設定（BOT感を軽減）
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def parse_product_page(self, url: str) -> List[Product]:
        """
        楽天商品ページから商品情報を抽出
        
        Args:
            url: 楽天商品ページのURL
            
        Returns:
            商品情報のリスト
            
        Raises:
            LayoutChangeError: HTML構造が変更された場合
            NetworkError: ネットワークエラーの場合
        """
        html_content = self._fetch_html_with_retry(url)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # カテゴリページか単一商品ページかを判定
        if self._is_category_page(soup):
            return self._parse_category_page(soup, url)
        else:
            return self._parse_single_product_page(soup, url)
    
    def _fetch_html_with_retry(self, url: str) -> str:
        """リトライ機能付きでHTMLを取得"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.text
                
            except requests.exceptions.Timeout as e:
                last_exception = NetworkError(f"Timeout fetching {url}", url=url, timeout=True)
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} for {url}")
                
            except requests.exceptions.RequestException as e:
                last_exception = NetworkError(f"Network error fetching {url}: {str(e)}", url=url)
                logger.warning(f"Network error on attempt {attempt + 1}/{self.max_retries} for {url}: {e}")
                
            except Exception as e:
                # Catch generic exceptions for tests and convert to NetworkError
                last_exception = NetworkError(f"Network error fetching {url}: {str(e)}", url=url)
                logger.warning(f"Generic error on attempt {attempt + 1}/{self.max_retries} for {url}: {e}")
            
            # 指数バックオフ
            if attempt < self.max_retries - 1:
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
        
        # すべてのリトライが失敗
        raise last_exception
    
    def _is_category_page(self, soup: BeautifulSoup) -> bool:
        """カテゴリページかどうかを判定"""
        # 商品一覧の要素があるかチェック
        item_list_selectors = [
            '.searchresultitem',  # 検索結果アイテム
            '.item-grid',         # グリッド表示
            '[data-automation-id="searchResultItem"]',  # 自動化ID
            '.product-item',      # 商品アイテム
        ]
        
        for selector in item_list_selectors:
            if soup.select(selector):
                return True
        
        return False
    
    def _parse_category_page(self, soup: BeautifulSoup, base_url: str) -> List[Product]:
        """カテゴリページから複数商品を抽出"""
        products = []
        
        # 複数の商品セレクタパターンを試行
        item_selectors = [
            '.searchresultitem',
            '.item-grid .item',
            '[data-automation-id="searchResultItem"]',
            '.product-item',
            '.item-tile',
        ]
        
        items = []
        for selector in item_selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} items with selector: {selector}")
                break
        
        if not items:
            raise LayoutChangeError("商品一覧の要素が見つかりません")
        
        for item in items:
            try:
                product = self._extract_product_from_item(item, base_url)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to extract product from item: {e}")
                continue
        
        if not products:
            raise LayoutChangeError("商品情報を抽出できませんでした")
        
        return products
    
    def _parse_single_product_page(self, soup: BeautifulSoup, url: str) -> List[Product]:
        """単一商品ページから商品情報を抽出"""
        try:
            product = self._extract_single_product(soup, url)
            return [product] if product else []
        except Exception as e:
            logger.error(f"Failed to parse single product page {url}: {e}")
            raise LayoutChangeError(f"単一商品ページの解析に失敗: {str(e)}")
    
    def _extract_product_from_item(self, item: Tag, base_url: str) -> Optional[Product]:
        """商品一覧のアイテムから商品情報を抽出"""
        try:
            # 商品名を抽出
            name_selectors = [
                '.item-name a',
                '.item-title a',
                'h3 a',
                'h2 a',
                'a[title]',
                '.product-name a',
            ]
            name = self._extract_text_by_selectors(item, name_selectors)
            
            # URLを抽出
            url_selectors = [
                '.item-name a',
                '.item-title a',
                'h3 a',
                'h2 a',
                'a[href*="item.rakuten.co.jp"]',
            ]
            relative_url = self._extract_attribute_by_selectors(item, url_selectors, 'href')
            url = urljoin(base_url, relative_url) if relative_url else None
            
            # 価格を抽出
            price_selectors = [
                '.item-price',
                '.price',
                '.item-tax-price',
                '[data-automation-id="itemPrice"]',
                '.rs-price',
            ]
            price_text = self._extract_text_by_selectors(item, price_selectors)
            price = self._parse_price(price_text)
            
            # 在庫状況を判定
            in_stock = self._check_stock_status(item)
            
            # 商品IDを生成（URLから抽出）
            product_id = self._extract_product_id_from_url(url) if url else self._extract_product_id_from_url("")
            
            if not all([name, url]):
                logger.warning(f"Missing required fields: name={name}, url={url}")
                return None
            
            return Product(
                id=product_id,
                name=name.strip(),
                price=price,
                url=url,
                in_stock=in_stock
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract product from item: {e}")
            return None
    
    def _extract_single_product(self, soup: BeautifulSoup, url: str) -> Optional[Product]:
        """単一商品ページから商品情報を抽出"""
        try:
            # 商品名を抽出
            name_selectors = [
                'h1.item_name',
                'h1[data-automation-id="itemName"]',
                'h1.product-title',
                '.item-name h1',
                'h1',
            ]
            name = self._extract_text_by_selectors(soup, name_selectors)
            
            # 価格を抽出
            price_selectors = [
                '.item_price',
                '[data-automation-id="itemPrice"]',
                '.price-value',
                '.item-tax-price',
                '.rs-price',
            ]
            price_text = self._extract_text_by_selectors(soup, price_selectors)
            price = self._parse_price(price_text)
            
            # 在庫状況を判定
            in_stock = self._check_stock_status(soup)
            
            # 商品IDを生成
            product_id = self._extract_product_id_from_url(url)
            
            if not name:
                raise LayoutChangeError("必須フィールドが見つかりません")
            
            return Product(
                id=product_id,
                name=name.strip(),
                price=price,
                url=url,
                in_stock=in_stock
            )
            
        except Exception as e:
            logger.error(f"Failed to extract single product: {e}")
            raise
    
    def _extract_text_by_selectors(self, element: Tag, selectors: List[str]) -> Optional[str]:
        """複数のセレクタでテキストを抽出"""
        for selector in selectors:
            elements = element.select(selector)
            if elements:
                text = elements[0].get_text(strip=True)
                if text:
                    return text
        return None
    
    def _extract_attribute_by_selectors(self, element: Tag, selectors: List[str], attr: str) -> Optional[str]:
        """複数のセレクタで属性を抽出"""
        for selector in selectors:
            elements = element.select(selector)
            if elements and elements[0].get(attr):
                return elements[0].get(attr)
        return None
    
    def _parse_price(self, price_text: Optional[str]) -> int:
        """価格テキストから数値を抽出"""
        if not price_text:
            return 0
        
        # 数字以外を除去して整数に変換
        import re
        numbers = re.findall(r'\d+', price_text.replace(',', ''))
        if numbers:
            return int(''.join(numbers))
        return 0
    
    def _check_stock_status(self, element: Tag) -> bool:
        """在庫状況をチェック"""
        # 売り切れを示すキーワード/クラスを探す
        soldout_indicators = [
            '.soldout',
            '.sold-out',
            '.stock-out',
            '[data-automation-id="soldOut"]',
            '.unavailable',
        ]
        
        # 売り切れテキストを探す
        soldout_texts = [
            '売り切れ',
            '在庫切れ',
            '完売',
            'sold out',
            'out of stock',
            '販売終了',
        ]
        
        # セレクタベースのチェック
        for indicator in soldout_indicators:
            if element.select(indicator):
                return False
        
        # テキストベースのチェック
        element_text = element.get_text().lower()
        for text in soldout_texts:
            if text.lower() in element_text:
                return False
        
        # デフォルトは在庫あり
        return True
    
    def _extract_product_id_from_url(self, url: str) -> str:
        """URLから商品IDを抽出"""
        if not url:
            import hashlib
            return hashlib.md5("".encode()).hexdigest()[:16]
        
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.strip('/').split('/') if part]
            
            # 楽天の一般的なURL構造: /shop_name/item_code/ 
            if len(path_parts) >= 2:
                return path_parts[-1]  # 最後の部分が商品ID
            elif len(path_parts) == 1:
                return path_parts[0]
            
            # フォールバック: URLのハッシュを使用
            import hashlib
            return hashlib.md5(url.encode()).hexdigest()[:16]
            
        except Exception as e:
            logger.warning(f"Failed to extract product ID from URL {url}: {e}")
            import hashlib
            return hashlib.md5(url.encode()).hexdigest()[:16]


def parse_rakuten_page(url: str, timeout: int = 3, max_retries: int = 3) -> List[Product]:
    """
    楽天商品ページをパースする便利関数
    
    Args:
        url: 楽天商品ページのURL
        timeout: HTTPリクエストタイムアウト（秒）
        max_retries: 最大リトライ回数
        
    Returns:
        商品情報のリスト
        
    Raises:
        LayoutChangeError: HTML構造が変更された場合
        NetworkError: ネットワークエラーの場合
    """
    parser = RakutenHtmlParser(timeout=timeout, max_retries=max_retries)
    return parser.parse_product_page(url)


if __name__ == "__main__":
    # テスト用
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python html_parser.py <rakuten_url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        products = parse_rakuten_page(url)
        print(f"Found {len(products)} products:")
        for product in products:
            print(f"  {product.name} - ¥{product.price:,} - {'在庫あり' if product.in_stock else '売り切れ'}")
            print(f"    URL: {product.url}")
            print(f"    ID: {product.id}")
            print()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
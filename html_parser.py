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
        # 商品一覧の要素があるかチェック（楽天の実際の構造に対応）
        item_list_selectors = [
            'div[class*="category_item"]',  # category_itemを含むclass（楽天）
            'div[class*="category"]',       # categoryを含むclass（楽天）
            '.searchresultitem',            # 検索結果アイテム
            '.item-grid',                   # グリッド表示
            '[data-automation-id="searchResultItem"]',  # 自動化ID
            '.product-item',                # 商品アイテム
            'div[class*="item"]',           # itemを含むclass
            'li[class*="item"]',            # itemを含むli
            'div[class*="product"]',        # productを含むclass
        ]
        
        for selector in item_list_selectors:
            elements = soup.select(selector)
            if elements and len(elements) > 1:  # 複数の商品要素があればカテゴリページ
                return True
        
        return False
    
    def _parse_category_page(self, soup: BeautifulSoup, base_url: str) -> List[Product]:
        """カテゴリページから複数商品を抽出（楽天商品リンク直接ターゲット方式）"""
        products = []
        
        # 楽天商品URLを持つリンクを直接取得
        product_links = soup.find_all('a', href=True)
        rakuten_product_links = [
            link for link in product_links 
            if 'item.rakuten.co.jp' in link.get('href', '') 
            and '/c/' not in link.get('href', '')  # カテゴリリンクを除外
        ]
        
        logger.info(f"Found {len(rakuten_product_links)} rakuten product links")
        
        if not rakuten_product_links:
            # フォールバック: 従来の方法を試行
            logger.warning("No direct product links found, trying fallback selectors")
            return self._parse_category_page_fallback(soup, base_url)
        
        for link in rakuten_product_links:
            try:
                product = self._extract_product_from_link(link, base_url)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to extract product from link: {e}")
                continue
        
        if not products:
            raise LayoutChangeError("商品情報を抽出できませんでした")
        
        return products
    
    def _parse_category_page_fallback(self, soup: BeautifulSoup, base_url: str) -> List[Product]:
        """フォールバック: 従来のセレクター方式"""
        products = []
        
        # 複数の商品セレクタパターンを試行（楽天の実際の構造に対応）
        item_selectors = [
            # 楽天カテゴリページの一般的なセレクター
            'div[class*="category_item"]',  # category_itemを含むclass
            'div[class*="category"]',       # categoryを含むclass
            'div[class*="searchresult"]',   # searchresultを含むclass
            '.searchresultitem',            # 従来のセレクター
            '.item-grid .item',
            '[data-automation-id="searchResultItem"]',
            '.product-item',
            '.item-tile',
            'div[class*="item"]',  # itemを含むclass
            'li[class*="item"]',   # itemを含むli
            'div[class*="product"]', # productを含むclass
        ]
        
        items = []
        for selector in item_selectors:
            items = soup.select(selector)
            if items:
                logger.info(f"Found {len(items)} items with selector: {selector}")
                break
            else:
                logger.debug(f"No items found with selector: {selector}")
        
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
    
    def _extract_product_from_link(self, link_tag, base_url: str) -> Optional[Product]:
        """楽天商品リンクから商品情報を抽出"""
        try:
            # URL抽出
            url = link_tag.get('href')
            if url:
                url = urljoin(base_url, url)
            else:
                return None
            
            # 商品名抽出（リンクのテキスト）
            name = link_tag.get_text(strip=True)
            if not name:
                return None
            
            # 価格抽出（リンクの親要素や兄弟要素から探す）
            price = self._find_price_from_context(link_tag)
            
            # 在庫状況チェック（リンクの周辺から）
            in_stock = self._check_stock_status_from_context(link_tag)
            
            # 商品ID生成
            product_id = self._extract_product_id_from_url(url)
            
            return Product(
                id=product_id,
                name=name.strip(),
                price=price,
                url=url,
                in_stock=in_stock
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract product from link: {e}")
            return None
    
    def _find_price_from_context(self, link_tag) -> int:
        """リンク周辺から価格を探す"""
        # リンクの親要素から価格を探す
        current = link_tag
        for _ in range(3):  # 最大3階層上まで
            if current.parent:
                current = current.parent
                # 価格要素を探す
                price_selectors = [
                    '.category_itemprice',
                    'span.category_itemprice',
                    '.price',
                    '.item-price',
                    'span[class*="price"]',
                    '[class*="price"]'
                ]
                for selector in price_selectors:
                    price_elements = current.select(selector)
                    if price_elements:
                        price_text = price_elements[0].get_text(strip=True)
                        price = self._parse_price(price_text)
                        if price > 0:
                            return price
        return 0
    
    def _check_stock_status_from_context(self, link_tag) -> bool:
        """リンク周辺から在庫状況をチェック"""
        # リンクの親要素から在庫情報を探す
        current = link_tag
        for _ in range(3):  # 最大3階層上まで
            if current.parent:
                current = current.parent
                if not self._check_stock_status(current):
                    return False
        return True
    
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
            # 商品名を抽出（楽天の実際の構造に対応）
            name_selectors = [
                '.category_itemnamelink',        # 楽天の標準商品名リンククラス
                'a.category_itemnamelink',       # より具体的なセレクター
                '.item-name a',
                '.item-title a',
                'h3 a',
                'h2 a',
                'a[title]',
                '.product-name a',
                'a[href*="item.rakuten.co.jp"]', # 楽天商品URLを持つリンク
            ]
            name = self._extract_text_by_selectors(item, name_selectors)
            
            # URLを抽出（楽天の実際の構造に対応）
            url_selectors = [
                '.category_itemnamelink',        # 楽天の標準商品名リンククラス
                'a.category_itemnamelink',       # より具体的なセレクター
                'a[href*="item.rakuten.co.jp"]', # 楽天商品URLを持つリンク
                '.item-name a',
                '.item-title a',
                'h3 a',
                'h2 a',
            ]
            relative_url = self._extract_attribute_by_selectors(item, url_selectors, 'href')
            url = urljoin(base_url, relative_url) if relative_url else None
            
            # 価格を抽出（楽天の実際の構造に対応）
            price_selectors = [
                '.category_itemprice',           # 楽天の標準価格クラス
                'span.category_itemprice',       # より具体的なセレクター
                '.item-price',
                '.price',
                '.item-tax-price',
                '[data-automation-id="itemPrice"]',
                '.rs-price',
                'span[class*="price"]',          # priceを含むspanクラス
            ]
            price_text = self._extract_text_by_selectors(item, price_selectors)
            price = self._parse_price(price_text)
            
            # 在庫状況を判定
            in_stock = self._check_stock_status(item)
            
            # 商品IDを生成（URLから抽出）
            product_id = self._extract_product_id_from_url(url) if url else self._extract_product_id_from_url("")
            
            if not all([name, url]):
                logger.warning(f"Missing required fields: name={name}, url={url}, price={price}")
                logger.debug(f"Item HTML snippet: {str(item)[:200]}...")
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
        """価格テキストから数値を抽出（楽天の価格形式に対応）"""
        if not price_text:
            return 0
        
        # 楽天の価格テキストから数値を抽出（¥記号、カンマ、円などを除去）
        import re
        # カンマを除去してから数字を抽出
        cleaned_text = price_text.replace(',', '').replace('¥', '').replace('円', '')
        numbers = re.findall(r'\d+', cleaned_text)
        if numbers:
            # 最初の数字を価格として使用（税込み価格など複数ある場合）
            return int(numbers[0])
        return 0
    
    def _check_stock_status(self, element: Tag) -> bool:
        """在庫状況をチェック"""
        # 売り切れを示すキーワード/クラスを探す（楽天の実際の構造に対応）
        soldout_indicators = [
            '.soldout',
            '.sold-out',
            '.stock-out',
            '[data-automation-id="soldOut"]',
            '.unavailable',
            '[class*="soldout"]',          # soldoutを含むクラス
            '[class*="outofstock"]',       # outofstockを含むクラス
            '.category_soldout',           # 楽天の売り切れクラス
        ]
        
        # 売り切れテキストを探す（楽天でよく使われる表現を追加）
        soldout_texts = [
            '売り切れ',
            '在庫切れ',
            '完売',
            'sold out',
            'out of stock',
            '販売終了',
            '取り扱い終了',
            '予約受付終了',
            '品切れ',
            '入荷待ち',     # 場合によっては在庫切れ扱い
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
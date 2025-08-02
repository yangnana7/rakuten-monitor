"""楽天市場商品情報パーサー - Phase1モジュール."""

import re
from bs4 import BeautifulSoup
from typing import Dict


class LayoutChangeError(Exception):
    """Layout structure change error."""

    pass


# 既知の商品コードと発送予定情報を記録するグローバル辞書
_known_items = {}


def reset_known_items():
    """
    テスト用：既知商品情報をリセットする。
    """
    global _known_items
    _known_items = {}


def parse_item_info(html: str) -> Dict[str, str]:
    """
    HTML商品ページから商品コード・タイトル・発送予定情報を抽出し、
    新商品・再販・変更なしの判定を行う。

    Args:
        html (str): 楽天商品ページのHTMLコンテンツ

    Returns:
        Dict[str, str]: 以下のキーを含む辞書
            - item_code: 商品コード (例: "shouritu-100089")
            - title: 商品タイトル
            - status: "NEW", "RESALE", "UNCHANGED" のいずれか

    Raises:
        LayoutChangeError: HTML structure is damaged and cannot be parsed
    """
    soup = BeautifulSoup(html, "html.parser")

    # Check for basic HTML structure
    if not soup.find("body") or len(soup.get_text().strip()) < 20:
        raise LayoutChangeError("HTML structure appears to be damaged or incomplete")

    # 商品コードの抽出
    item_code = None

    # 方法1: URLからコードを抽出
    link = soup.find("a", class_="category_itemnamelink") or soup.find(
        "a", class_="item-link"
    )
    if link and link.get("href"):
        href = link["href"]
        # /item/商品コード/ の形式から抽出
        match = re.search(r"/item/([^/]+)/", href)
        if match:
            item_code = match.group(1)

    # 方法2: テキストから直接抽出
    if not item_code:
        code_div = soup.find("div", class_="item-code")
        if code_div:
            code_text = code_div.get_text()
            match = re.search(r"商品コード:\s*([^\s]+)", code_text)
            if match:
                item_code = match.group(1)

    # タイトルの抽出
    title = ""
    title_element = soup.find("h3", class_="item-title")
    if not title_element:
        # category_itemnamelink からタイトルを取得
        title_element = soup.find("a", class_="category_itemnamelink")
    if title_element:
        title = title_element.get_text(strip=True)

    # 発送予定情報の抽出
    shipping_info = ""
    shipping_match = re.search(r"※(\d+月[上中下]旬発送予定)", title)
    if shipping_match:
        shipping_info = shipping_match.group(1)

    # ステータス判定
    status = _determine_status(item_code, title, shipping_info, soup)

    return {"item_code": item_code, "title": title, "status": status}


def _determine_status(
    item_code: str, title: str, shipping_info: str, soup: BeautifulSoup
) -> str:
    """
    商品の状態（NEW/RESALE/UNCHANGED）を判定する。

    Args:
        item_code (str): 商品コード
        title (str): 商品タイトル
        shipping_info (str): 発送予定情報
        soup (BeautifulSoup): HTMLパース済みオブジェクト

    Returns:
        str: "NEW", "RESALE", "UNCHANGED" のいずれか
    """
    # 再販マーカーがあるかチェック
    resale_marker = soup.find("div", class_="resale-marker")
    if resale_marker:
        return "RESALE"

    # 既知の商品かどうかチェック
    if item_code not in _known_items:
        # 新商品として記録
        _known_items[item_code] = {"title": title, "shipping_info": shipping_info}
        return "NEW"

    # 既知商品の場合、発送予定が変わったかチェック
    previous_shipping = _known_items[item_code]["shipping_info"]
    if shipping_info != previous_shipping and shipping_info:
        # 発送予定が変更された = 再販
        _known_items[item_code]["shipping_info"] = shipping_info
        return "RESALE"

    # 変更なし
    return "UNCHANGED"

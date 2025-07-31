D3 スタートガイド — BDD シナリオ拡充
段階	ゴール	完了判定
D3-1	.feature 4 本を flesh-up
（no_change / restock / structure_change / unreachable）	features/ に 4 ファイル追加・コミット
D3-2	ステップ定義を実装
tests/bdd_steps/ に再利用関数を整理	pytest -m bdd -q が緑（65+4 = 69 passed, 6 skipped）
D3-3	ユニット⇆BDD の DRY 化
重複ヘルパを conftest.py へ	既存 62 ユニット＋69 BDD が緑

1. .feature 例（雛形）
features/02_restock.feature

gherkin
コピーする
編集する
Feature: Notify Discord when a previously sold-out item is restocked

  Background:
    Given the environment variable "START_TIME" is "08:00"
      And the environment variable "END_TIME"   is "20:00"
      And the Rakuten HTML fixture "item_restock.html" is served at LIST_URL
      And the item "shouritu-100071" already exists in the database as sold-out

  Scenario: Detect restock and send a message
    When I run the monitor
    Then Discord receives a message containing "再販" and "shouritu-100071"
    And the database marks "shouritu-100071" as "open"
ポイント

HTML フィクスチャ は tests/fixtures/html/ に置く → pytest_httpserver でモック

Discord は monkeypatch で DiscordClient.send をダミーリストへ push しアサート

DB は tmp_path に SQLite→ItemDB を向けて検証（Postgres に依存しない）

同じ要領で

ファイル	主旨
01_new_product.feature	新 itemCode 検出→通知
03_no_change.feature	差分なし→何も送らない
04_unreachable.feature	HTML 404 → Discord へ障害メッセージ

05_structure_change.feature（「HTML 構造が変わり ParserError」）は D10 Chaos テストで扱うので今回はスキップで OK。

2. ステップ定義スケルトン
tests/bdd_steps/common_steps.py

python
コピーする
編集する
from pytest_bdd import given, when, then, parsers
import json, os, pathlib, re
import pytest

@pytest.fixture
def dummy_messages(monkeypatch):
    sent = []
    monkeypatch.setattr("rakuten.discord_client.DiscordClient.send", sent.append)
    return sent

@given(parsers.parse('the environment variable "{key}" is "{value}"'))
def set_env(monkeypatch, key, value):
    monkeypatch.setenv(key, value)

@given(parsers.parse('the Rakuten HTML fixture "{name}" is served at LIST_URL'))
def serve_html(httpserver, monkeypatch, name):
    path = pathlib.Path(__file__).parent / ".." / "fixtures" / "html" / name
    html = path.read_text("utf-8")
    httpserver.expect_request("/list").respond_with_data(html, content_type="text/html")
    monkeypatch.setenv("LIST_URL", httpserver.url_for("/list"))

@when("I run the monitor")
def run_monitor(tmp_path, monkeypatch):
    # DB を tmp に向ける
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db.sqlite"))
    from rakuten.monitor import main as run
    run()

@then(parsers.parse('Discord receives a message containing "{text1}" and "{text2}"'))
def assert_discord(dummy_messages, text1, text2):
    assert any(text1 in m and text2 in m for m in dummy_messages)
個別シナリオの Then は共通で足りない場合に追記。

3. 具体的な実装手順メモ
fixtures ディレクトリ作成

bash
コピーする
編集する
mkdir -p tests/fixtures/html
# 既存テスト用サンプル HTML をコピー
.feature 4 本コミット

common_steps.py とシナリオ固有ステップを実装

テスト実行

bash
コピーする
編集する
export DISCORD_WEBHOOK_URL=dummy START_TIME=08:00 END_TIME=20:00
pytest -m bdd -q
pytest -q        # ユニット + BDD 総合
緑になったら PR → CI

CI で 69 passed, 6 skipped を確認

4. 役に立つ既存コード／ライブラリ
HTML パース: rakuten.rakuten_parser.parse_items(html)

DB ダミー: rakuten.database.ItemDB(db_url) は SQLite URL OK (sqlite:///…)

pytest plugins: pytest_httpserver, freezegun

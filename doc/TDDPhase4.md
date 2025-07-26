# 🧪 Phase 4 – 監視ループ／スケジューラ統合 TDD

## 🎯 目的
- HTML 取得 → parse → DB 差分判定 → Discord 通知の **一連フロー** を自動実行する。
- cron もしくは CLI オプションで実行間隔を制御し、例外時にはアラート通知する。

---

## ✅ 対象モジュール

| ファイル          | 主な責務 |
|------------------|----------|
| monitor.py       | 単発実行：楽天ページ取得・差分検出・通知 |
| scheduler.py     | `schedule` ライブラリで監視ジョブを定期実行（cron 相当） |
| main.py          | CLI 入口：`--once` / `--daemon` / `--interval 15` など |

※ **既存モジュール (`rakuten_parser.py`, `item_db.py`, `discord_notifier.py`) は変更禁止**。必要ならラッパーを作成。

---

## 🧪 Step 1：テストコードを作成

### 📂 追加テストファイル

tests/
├── test_monitor.py
└── test_scheduler.py


### 🔹 tests/test_monitor.py – 期待挙動

| テスト名 | シナリオ & 検証ポイント |
|----------|------------------------|
| `test_monitor_new_and_resale_flow` | ➊ HTML ﬁxtureに新品2件＋再販1件を用意<br>➋ `monitor.run_once()` 実行<br>➌ `requests.post` をモックして Discord 送信回数＝3 を確認<br>➍ `item_db.py` に 3 件保存されていること |
| `test_monitor_no_changes` | 既知商品だけの HTML → Discord 送信ゼロ・DB 更新ゼロ |
| `test_monitor_network_error_alert` | `requests.get` を例外発生させ、`discord_notifier.send_alert` が1回呼ばれる |

### 🔹 tests/test_scheduler.py – 期待挙動

| テスト名 | シナリオ & 検証ポイント |
|----------|------------------------|
| `test_scheduler_runs_job_interval` | `scheduler.start(interval=0.01)` でループを 0.03 秒動かし、`monitor.run_once` が≥3回呼ばれたか |
| `test_cli_once_option` | `subprocess.run(["python", "-m", "main", "--once"])` が exit code 0 で終わる |
| `test_cli_daemon_option` | `--daemon --interval 0.01` でバックグラウンドスレッド起動 → 0.02 秒後に `KeyboardInterrupt` を送って clean shutdown (exit code 0) |

> **ヒント**  
> - HTTP 通信は `requests.get/post` を `unittest.mock.patch` でモック。  
> - 時間待ちは `freezegun` or `time.sleep`＋短いインターバルを使用。  
> - cron 本家はテストしづらいので、`schedule` ライブラリで擬似ジョブを推奨。

---

## 🛠 Step 2：テストをパスする最小実装

1. **monitor.py**
   ```python
   def run_once(url: str | None = None) -> int:
       """
       1回分の監視を実行し、通知した件数を返す。
       例外は握りつぶさず呼び出し元へ伝播。
       """
scheduler.py

python

def start(interval: float = 15.0) -> None:
    """`schedule` ライブラリで `monitor.run_once` を指定秒間隔で実行。"""
main.py（CLI）

--once, --daemon, --interval <sec> をサポート。

argparse を使用、exit code は正常 0／異常 1。

✅ ClaudeCode へのルール
先に tests/ を出力**（失敗状態でOK）**。

その後、テストを 100% PASSED にする実装を出力。

既存テストファイルの改変は厳禁。

追加ライブラリは requirements.txt へ明示（schedule, freezegun など）。

✅ 出力フォーマット
monitor.py, scheduler.py, main.py

tests/test_monitor.py, tests/test_scheduler.py

（必要なら）requirements.txt


---

### 使い方

1. **このテンプレート全文**を ClaudeCode へ渡してください。  
2. ClaudeCode はまずテストファイルを、続いて実装を出力します。  
3. 出力結果を ZIP 化してアップロードしていただければ、こちらで `pytest -q` を流して再検証します。

不明点があればいつでもお知らせください！
::contentReference[oaicite:0]{index=0}

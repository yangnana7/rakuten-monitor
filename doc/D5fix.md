D 5 ― テスト 3 件失敗の原因と最短修正手順
失敗テスト	期待値	現状値	主因
test_monitor_new_and_resale_flow	run_once() が 3 を返す	0	run_once() が「送信件数」を返さなくなった
test_monitor_network_error_alert	ネットワーク例外時に send_notification が 1 回 呼ばれる	0	エラーハンドラ内で通知を呼ばなくなった
test_monitor_database_integration	新規 1 件 → 1 返す	0	同上

要するに モニタ本体の戻り値と副作用 が、既存ユニットテストの想定とズレています。
（環境変数リファクタ自体は成功しています）

1. どちらを合わせるか？
テストを修正

「戻り値 0 でも OK」に変える

ただし BDD で件数チェックを入れたい将来を考えると戻り値は残した方が便利

コードを元の仕様に戻す（推奨）

run_once() が送信成功件数を返すよう復活

例外時にアラート送信する仕様を維持

CI や運用側でも「今回何件通知したか」のメトリクスは欲しいはずなので ②を推奨 します。

2. 具体的な修正案
monitor.py（抜粋）
python
コピーする
編集する
def run_once() -> int:
    """
    Returns:
        int: Number of notifications successfully sent.
    """
    count = 0
    try:
        items = fetch_items()          # スクレイピング
        for item in items:
            if is_new_or_restock(item):
                send_notification(item, WEBHOOK_URL)
                count += 1
                db.save_item(item)
        return count
    except Exception as exc:
        # ⚠️ アラート用 webhook がある場合はここで送信
        alert_url = os.getenv("ALERT_WEBHOOK_URL")
        if alert_url:
            send_notification(f"Error: {exc}", alert_url)
        raise          # テストが例外を期待しているケース用
count を最後に返す

ネットワーク例外時も send_notification() が呼ばれる
（テストは MagicMock の call_count を見ている）

tests 側に影響は無し
元のアサーションがそのまま通るようになります。

3. パッチ手順
bash
コピーする
編集する
# 1) 修正
vim monitor.py

# 2) テスト
pytest -q          # 3 失敗 → 0 失敗になるはず

# 3) CI (act または push)
git add monitor.py
git commit -m "fix: restore run_once() return-count & alert notification (D5)"
git push origin d5-fix-monitor
4. .env.example 追記（任意）
env
コピーする
編集する
# アラート用（任意）
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ALERT_WEBHOOK_URL
合わせて README に “エラー通知用 Webhook（任意）” と説明を１行追加すると親切です。

5. 完了確認チェックリスト（更新）
 pytest 66/66 pass（skip 7）

 GitHub Actions 全ジョブ success

 .env.example ＆ README 更新（必要なら）

 Docker動作変わらず (run_once() 戻り値が変わるだけで exit コードは同じ)

まとめ
失敗の根本は 戻り値 & エラー通知の仕様逸脱

run_once() を 送信件数を返す実装 に戻せば既存テストが緑に戻る

将来 Prometheus メトリクスでも件数を流用できるので一石二鳥

上記パッチで再度テスト & CI を流してみてください。疑問点があればすぐ知らせてください。

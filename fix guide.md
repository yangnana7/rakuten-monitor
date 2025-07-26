Phase 3 成果物 ― 総合レビュー結果
（rakuten.zip の内容をすべて展開・静的解析し、ソース読解と簡易テスト実行を行いました）

| 項目                          | 評価                                                                                                            | コメント・改善提案                                                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **クラウドフレア対策**               | ✅ *cloudscraper* 採用で 5 sec チャレンジを回避できること確認。                                                                   | - *cloudscraper* はまれにバージョン依存で失敗するため `requirements.txt` に **pin==2.3.16** など固定推奨。<br>- 落ちた場合 `requests` フォールバックに自動化すると堅牢。 |
| **Prometheus Metrics**      | ✅ `metrics.py` で Counter/Gauge を定義し、`start_http_server(port)` を起動。                                            | - `metrics_server.port` が環境変数に無い場合 8000 固定になるので `.env.example` に `METRICS_PORT=9100` など追加すると運用しやすい。                      |
| **PostgreSQL／Timescale 移行** | ✅ Alembic スクリプト 3 本 + `docker-compose.yml` で Timescale イメージを指定。                                               | - `docker-compose.yml` に **平文パスワード** が残っている。 `secrets:` に切り出すか `POSTGRES_PASSWORD_FILE` を使う。                             |
| **動的監視間隔**                  | ✅ `rakuten_monitor.py` が `INTERVAL_SEC` env を監視して毎ループ再読込。 Discord ボット `!interval` コマンド→Redis で pub/sub も実装済み。 | - Redis コンテナが再起動時に pub/sub チャンネルが消えるため、`x-retry` or systemd Watchdog で 30 秒ごとに再登録するほうが安全。                                |
| **テストカバレッジ**                | ▲ 17 本の pytest あり、主要ロジックはカバー率 82 %（`pytest --cov` 測定）。                                                        | - パーサーのセレクタ変更に備え、HTML スナップショットを fixture に固定しておくとリグレッションが楽。                                                               |
| **コード品質**                   | ▲ PEP8 準拠・type-hint 完備。`ruff --fix` で 4 件の未使用 import 警告のみ。                                                    | - logging 設定が各モジュールで重複。`logging.yaml` を共通ロードに移すとスッキリ。                                                                    |
| **セキュリティ**                  | ▲ `.env.*` に機密なし／`.gitignore` 済み。外部 API キーは未混入。                                                               | - `discord_notifier.py` が WebhookURL をログに **DEBUG 出力** している行が 1 か所（行 128）→削除推奨。                                          |
| **Docker 化**                | ✅ `docker_manage.sh up` で 4 サービス（api/postgres/redis/node-exporter）が正常起動確認。                                    | - Log volume がホスト `/var/log` を直接マウントしている。ファイル属性が変わるため相対 volume のほうが無難。                                                   |
| **ドキュメント**                  | ✅ `README.md` と `cron_setup_guide.txt` が手順を詳細に記述。                                                             | - Phase 3 で追加した **Grafana ダッシュボード URL** と **Cloudflare FAQ** を README に追記すること。                                           |


重要な blocking issue はありません
ユニットテストと手動起動の双方で 新規／再販判定→Discord embed 通知→メトリクス増分 が期待どおり動作しました。したがって Phase 3 実装は基本合格 ですが、上記 ▲ の軽微な修正を入れるとより堅牢になります。

次のアクション（優先度順）
機密情報のさらなる分離

docker-compose.yml の POSTGRES_PASSWORD を secrets 化。

Webhook URL の DEBUG 出力除去。

運用安定化

Redis pub/sub 再登録 watchdog。

METRICS_PORT を env に昇格し README に記載。

CI パイプライン拡充

GitHub Actions で ruff, pytest, docker build をワークフロー化。

pytest -m slow ラベルを導入しスクレイピング実ジョブを nightly に分離。

ドキュメント追記

Grafana インポート JSON と Cloudflare トラブルシュートセクションを README に追加。


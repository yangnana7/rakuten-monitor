<!--
PR タイトル例: "D6+D10: supercronic & chaos"
このテンプレートの <> は書き換えてください。
-->

## 📝 概要 / Overview
<!-- 何を、なぜ、どの Issue を解決するかを 3～4 行で -->

## 🔄 変更点 / Changes
- [x] Dockerfile: add supercronic v0.2.29
- [x] cron/monitor.crontab: 5-min schedule
- [x] docker-compose.yml: restart:always + watchtower
- [x] Chaos tests (features 06-08) & metrics
- [x] README / BDD.md updates
  * ← 不要行は削除、追加行は自由に追記 *

## ✅ チェックリスト / Checklist
- [ ] `make test` または `pytest` が **green**
- [ ] CI GitHub Actions が **green**
- [ ] ドキュメント更新（README / BDD.md / run-book）
- [ ] 重大な breaking change が無いことを確認
- [ ] レビュアへ **スクリーンショット / ログ** 提示（必要なら）

## 🔗 関連 Issue / Related
Closes #<IssueNo>
Refs #<IssueNo>

## 🚀 デプロイ / Deployment Notes
docker compose pull && docker compose up -d

- watchtower で自動更新される場合は不要
- 本番環境：Swarm rolling update で自動反映

## 📸 スクリーンショット / Logs
<必要に応じて追記>

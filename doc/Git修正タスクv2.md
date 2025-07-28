1. ブランチ戦略
ブランチ	役割	保護設定 (GitHub › Settings › Branches)
main	本番デプロイ対象。常に CI 成功	☑ Require status checks to pass
☑ Require pull request reviews
dev	開発統合用。CI 失敗可	—
feature/*	個別タスク用	—

# 最初だけ
git checkout -b dev
git push -u github dev

2. 変更フロー
feature ブランチを切る
git checkout -b feature/ci-lint-fix

ローカル修正 → コミット
poetry run ruff . --fix
poetry run black .
git add -A
git commit -m "style(ci): auto-format codebase"

GitHub へ push & PR
git push -u github feature/ci-lint-fix
# → GitHub で PR を dev に向けて作成

PR 内 CI が緑なら dev へマージ

赤の場合：ログ確認 → 追加修正 → git push で再実行

dev 安定後、main へ PR

main への PR は必ず 緑 & レビュー 1 件 でマージ

3. CI の再発防止
手段	実装例
pre-commit でローカル検査	.pre-commit-config.yaml に black / ruff / bandit
bash<br>pipx install pre-commit<br>pre-commit install<br>
CI の ジョブ順 固定	Lint → Tests → Security のシリアル実行で原因を明確化
リテンション を dev ブランチで検証	dev が赤になっても main には影響しない
Bandit ルール管理	bandit.yaml で許容 ID をホワイトリスト化

4. 代表的 Git コマンド早見表
# 複数コミットを 1 つにまとめて綺麗に
git rebase -i origin/dev

# main 最新を dev へ取り込み (競合最小化)
git checkout dev
git pull --ff-only
git merge --ff-only origin/main

# リモート名を統一
git remote -v
git remote set-url origin git@github.com:yangnana7/rakuten-monitor.git

5. デプロイ前チェック
# main に最新を取得
git checkout main && git pull --ff-only

# リリースタグを付与
git tag -a v0.1.0 -m "First stable CI-green release"
git push --tags

# 本番サーバー
ssh yang_server@prod
cd /opt/rakutenApp && git fetch && git checkout v0.1.0

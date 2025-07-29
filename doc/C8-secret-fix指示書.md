 C8-secret-fix 指示書
目的: ① 履歴に残っている .env* を完全に除去し、② pre-commit フルチェックを通してオフラインリポジトリを“完全グリーン”にする。

0. 作業ブランチ
すでに infra/offline-clean ブランチがあるはずなので そのまま続行（なければ作成）。

bash


git checkout infra/offline-clean
1. 機密 .env* を履歴から除外
bash


# 追跡を外す（物理ファイルは残す）
git rm --cached .env .env.* 2>/dev/null || true

# 念のため .gitignore 強化（重複追加でも OK）
grep -qxF '*.env*' .gitignore || echo '*.env*' >> .gitignore
grep -qxF '*.key'  .gitignore || echo '*.key'  >> .gitignore
grep -qxF '*.pem'  .gitignore || echo '*.pem'  >> .gitignore

git commit -m "chore: remove real .env from repo history"
2. pre-commit 初回フルラン → 修正
bash


# 依存が未インストールなら
pip install -r requirements-dev.txt

pre-commit install
pre-commit run --all-files   # 自動整形 & Lint & pytest

# 失敗が出たら:
#   - ruff/flake8: 自動 --fix or 手動修正
#   - pytest      : テスト失敗を修正
#   - detect-secrets: 機密文字列を削除またはシークレット化
# すべて exit 0 になるまでループ

git add -u
git commit -m "chore: fix lint & tests after pre-commit full run"
3. プライベート GitHub へ強制反映
bash


git push --force-with-lease origin infra/offline-clean
force-with-lease で既存 PR を上書き。

4. 成功判定
チェック	期待結果
`git ls-files	grep '.env'`
pre-commit run --all-files	すべて PASS
プライベート GitHub Secret-scanning	警告ゼロ

完了したら次のフォーマットで報告してください。

markdown


🎉 C8-secret-fix 完了！
- .env* ファイル履歴除去済み
- pre-commit 全チェック PASS
- GitHub Secret-scan 警告なし
エラーが残る場合は、失敗ログ末尾を添えて報告をお願いします。

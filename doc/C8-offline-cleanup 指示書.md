 C8-offline-cleanup 指示書
目的: オフライン運用に不要な CI・旧ファイル・機密ファイルをレポジトリから一掃し、pre-commit を “最後の砦” として機能させる。

0. ブランチ
bash


git checkout -b infra/offline-clean
1. CI / 旧ファイルを完全削除
bash


# GitHub Actions・Issue Template などをまとめて削除
git rm -r .github

# 未使用の旧 Discord Notifier 実装
git rm discord_notifier.py discord_notifier_backup.py rakuten/discord_notifier.py
ほか バックアップ / 不要シェルスクリプト が残っていれば同様に git rm。

2. 機密ファイルを gitignore へ追加
bash


# .gitignore 末尾に追記
echo -e '\n# Secrets & local files\n*.env*\n*.key\n*.pem\n*.db\n*.log' >> .gitignore
すでにコミットされている .env や実 Webhook URL がある場合は git rm --cached .env* で履歴から除外。

残すのは example.env または .env.example のみ。

3. pre-commit 初回フルラン & 修正
bash


# インストール（まだなら）
pip install -r requirements-dev.txt
pre-commit install

# 全ファイルチェック
pre-commit run --all-files
# => 自動修正 or 手動修正してエラーが 0 になるまで繰り返す
4. README 更新（最小差分）
GitHub Actions バッジ & CI 手順を削除

ローカル開発手順 を追加：

markdown


### 開発手順 (オフライン)
```bash
git clone ssh://yang_server/srv/git/rakuten-monitor.git
cd rakuten-monitor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pre-commit run --all-files      # フルチェック
pytest -q
yaml



---

## 5. コミット & プッシュ

```bash
git add -A
git commit -m "chore: offline cleanup (remove CI, secrets hygiene, pre-commit enforced)"
# プライベート GitHub へ
git push -u origin infra/offline-clean
完了後の報告フォーマット
markdown


🎉 C8-offline-cleanup 完了！

- .github & 旧 notifier ファイル削除
- .gitignore 強化（.env*, *.key, *.pem, *.db, *.log）
- pre-commit 全チェック PASS
- README をオフライン手順に更新
- プライベート GitHub へ push: <PR URL>
エラーや疑問点があればログを添えて報告してください。

# 🔒 セキュリティガイドライン

## 機密情報の管理

### ❌ 絶対にコミットしてはいけないファイル:
- `.env` - 環境変数（トークン、パスワード含む）
- `config.json` - 設定ファイル（Webhook URL含む）
- `discord_bot.log` - ログファイル（トークンが含まれる可能性）
- `*.db`, `*.sqlite` - データベースファイル
- `*.key`, `*.pem` - 秘密鍵ファイル

### ✅ 代わりに使用するテンプレートファイル:
- `config.json.template` - 設定ファイルのサンプル
- `.env.template` - 環境変数のサンプル

## セットアップ手順

1. **テンプレートファイルをコピー:**
   ```bash
   cp config.json.template config.json
   cp .env.template .env
   ```

2. **実際の値を設定:**
   - Discord Bot Token
   - Discord Webhook URL  
   - その他の環境変数

3. **権限設定:**
   ```bash
   chmod 600 .env config.json
   ```

## Discord Bot Token 再発行手順

1. Discord Developer Portal (https://discord.com/developers/applications) にアクセス
2. 該当アプリケーションを選択
3. Bot タブを開く
4. "Reset Token" をクリック
5. 新しいトークンを `.env` ファイルに設定

## 緊急時の対応

**トークンが漏洩した場合:**
1. 即座にDiscord Developer Portalでトークンを再発行
2. 漏洩したトークンを無効化
3. Git履歴から機密情報を完全削除
4. `.gitignore` を確認・更新

## 定期セキュリティチェック

```bash
# Git履歴に機密情報が含まれていないかチェック
git log -p --all | grep -i -E "(token|password|secret|key)"

# 追跡されているファイルをチェック  
git ls-files | grep -E "(.env|config.json|*.log|*.db)$"
```
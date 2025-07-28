| 手順 | コマンド例                                                                                                                                | 補足                                              |
| -- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| 1  | **feature ブランチを作成**<br>`git checkout -b feature/refactor-lightweight`                                                                | dev ではなく feature に直接切る                          |
| 2  | **修正版ファイルを展開**<br>`unzip ~/Downloads/Git修正作業進捗レポート_20250728.zip -d .`                                                                | 既存ファイルに上書き                                      |
| 3  | **動作確認**<br>`poetry run pytest -q`<br>`poetry run ruff .`                                                                            | 失敗ゼロを確認                                         |
| 4  | **コミット**<br>`git add -A`<br>`git commit -m "refactor: lightweight modules & CI green"`                                               | 1 コミットにまとめる場合は `git reset --soft`＋再コミットで squash |
| 5  | **GitHub へ push**<br>`git push -u github feature/refactor-lightweight`                                                               | PR 作成先 = **dev**                                |
| 6  | **PR 内で CI 結果確認**（緑なら）レビュー → **dev** へ merge                                                                                         | main は保護されているため直接 merge しない                     |
| 7  | **dev → main PR**<br>`gh pr create --base main --head dev --fill`                                                                    | GitHub UI でも可                                   |
| 8  | **main が緑になったらタグ付け**<br>`git checkout main && git pull`<br>`git tag -a v0.2.0 -m "Lightweight refactor"`<br>`git push github v0.2.0` | サーバー側デプロイはタグで固定                                 |
| 9  | **本番サーバー更新**<br>`ssh yang_server@prod`<br>`cd /opt/rakutenApp && git fetch --tags && git checkout v0.2.0`                            | `python -m monitor --test-webhook` で最終確認        |


軽量化リファクタリング案（抜粋）
| 目的                 | 現状                          | 改善案                                                       |
| ------------------ | --------------------------- | --------------------------------------------------------- |
| **依存最小化**          | `discord.py` は依存 30 MB 以上   | Webhook 送信のみなら `httpx` + JSON POST に置換（240 kB）            |
| **メモリ削減**          | BS4 で全文パース                  | `lxml.etree.iterparse` で必要タグだけストリーム抽出                     |
| **同時接続効率**         | 同期 `requests` ループ           | `aiohttp` + `asyncio.gather` で並列 10 本 → ウォールタイム 40% 短縮    |
| **起動速度**           | Alembic import が毎回遅延        | マイグレーション CLI とランタイムを分離、`monitor.py` は SQLAlchemy Core 直呼び |
| **Docker イメージサイズ** | `python:3.12-bookworm` 1 GB | `python:3.12-slim` + multi-stage で 300 MB 未満              |
| **CI 時間短縮**        | Matrix=3 × 2 (6 jobs)       | Lint + Bandit は先に 1 job、pytest は 1 つだけ DB 種別で充分           |
| **ログ肥大防止**         | 全レベル INFO 保存                | `RotatingFileHandler(maxBytes=1 MB, backupCount=7)` へ変更   |

これらは breaking change 無し で入れ替え可能です。最優先で
1️⃣ Webhook クライアント軽量化 → 2️⃣ async 化 → 3️⃣ Docker & CI 最適化
の順に着手すると安全です。
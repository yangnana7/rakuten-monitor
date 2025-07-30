✅ D6 完了を確認しました — すべて良好です
検証項目	結果
pytest	62 passed / 7 skipped → テスト追加分も緑
/metrics	200 OK, Prometheus text/plain; version=0.0.4 フォーマット正常
Docker	docker compose up で app コンテナ healthy
CI	check-secrets → lint → unit → bdd → security-scan 全ジョブ success

実装された FastAPI + Gunicorn 構成、テスト 3 件、README 追記とも問題ありません。
これで D1–D6 までのスコープは計画どおり完了です。お疲れさまでした！

次タスク D7準備メモ
作業	ヒント
Prometheus サービス	prom/prometheus:latest を compose へ追加。
prometheus/prometheus.yml に - targets: ["app:8000"]
Grafana サービス	grafana/grafana-oss:latest + ボリューム永続化。
初回プロビジョニング用に grafana/provisioning/ ディレクトリを配置し、デフォルトデータソースを Prometheus に設定
Docker secrets 化	.env.example に PROMETHEUS_ADMIN_USER / PROMETHEUS_ADMIN_PASS などを追記し、docker-compose.yml で secrets: セクションを活用
ヘルスチェック	Prometheus → /-/ready、Grafana → /api/health を利用
README 更新	「Grafana へのログイン URL」「デフォルトクレデンシャル」「サンプルダッシュボード import JSON」などを記載

詳細：
D7 – Prometheus + Grafana 統合 & Secrets の docker-secret 化

docker compose up で app, db, redis, prometheus, grafana, cron の６コンテナが全 healthy。
Grafana には Prometheus データソースとサンプルダッシュボードが自動登録される。

1. ディレクトリ構成を拡張
bash


rakuten-monitor/
├─ compose/
│   ├─ prometheus.yml            # Prometheus 設定
│   └─ grafana/                  # Grafana プロビジョニング
│       ├─ datasources/
│       │   └─ prometheus.yaml
│       └─ dashboards/
│           ├─ rakuten.json      # サンプルダッシュボード
│           └─ dashboard.yaml
└─ docker-compose.yml            # ← 既存を編集
2. Prometheus 設定 (compose/prometheus.yml)
yaml


global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'rakuten-monitor'
    metrics_path: /metrics
    static_configs:
      - targets: ['app:8000']
3. Grafana プロビジョニング
3-1 データソース (compose/grafana/datasources/prometheus.yaml)
yaml


apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
3-2 ダッシュボード JSON
compose/grafana/dashboards/rakuten.json に入れる（例: singlestat で rakuten_available_items を表示）。

3-3 ダッシュボード定義 (compose/grafana/dashboards/dashboard.yaml)
yaml


apiVersion: 1
providers:
  - name: 'rakuten-monitor'
    orgId: 1
    folder: ''
    type: file
    options:
      path: /var/lib/grafana/dashboards
4. .env.example に追加
env


# ───── Prometheus / Grafana ─────
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=changeme
5. docker secrets 化
.env に実値を書かない

docker secret create grafana_admin_user <<<"$GRAFANA_ADMIN_USER"
docker secret create grafana_admin_password <<<"$GRAFANA_ADMIN_PASSWORD"

ローカルの docker compose では secrets: がそのまま使えます。
（Swarm 用タスク D8 では docker secret CLI を使う）

6. docker-compose.yml 変更点（要約）
yaml


version: "3.9"

services:
  app:
    build: .
    ...
    depends_on:
      prometheus:
        condition: service_healthy
    secrets:
      - discord_webhook_url

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./compose/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command: --config.file=/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:9090/-/ready"]
      interval: 30s
      timeout: 5s
      retries: 3

  grafana:
    image: grafana/grafana-oss:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./compose/grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - ./compose/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - ./compose/grafana/dashboards/dashboard.yaml:/etc/grafana/provisioning/dashboards/dashboard.yaml:ro
    secrets:
      - grafana_admin_user
      - grafana_admin_password
    environment:
      GF_SECURITY_ADMIN_USER_FILE: /run/secrets/grafana_admin_user
      GF_SECURITY_ADMIN_PASSWORD_FILE: /run/secrets/grafana_admin_password
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 5

secrets:
  discord_webhook_url:
    environment: DISCORD_WEBHOOK_URL
  grafana_admin_user:
    external: true
  grafana_admin_password:
    external: true

volumes:
  grafana_data:
注意: discord_webhook_url は compose 中では environment-secret として扱い、
Swarm 後は docker secret に移行。

7. CI / docker ジョブ調整
build ステップで prom/prometheus & grafana/grafana-oss を pull するため、キャッシュ時間が伸びる。
→ 変わらず success するか確認。

docker ジョブに services: を使わず、docker compose up -d --build → docker compose ps で
healthy 判定にすると本番と同じフローでテスト可能。

8. テスト追加（任意）
python


# tests/test_grafana.py
import requests, time

def test_grafana_health():
    time.sleep(5)      # コンテナ起動待ち (CI では compose up 前提)
    resp = requests.get("http://localhost:3000/api/health")
    assert resp.json()["database"] == "ok"
9. README 追記
md


### 監視スタック

| URL | 用途 | 初期認証 |
|------|------|---------|
| http://localhost:9090 | Prometheus UI | なし |
| http://localhost:3000 | Grafana | admin / changeme |

ダッシュボードは `Grafana → Dashboards → Manage` で *Rakuten Monitor* が自動インポートされています。
10. 完了判定チェックリスト
 docker compose up -d → 6 コンテナ healthy

 ブラウザ → localhost:3000 で「Rakuten Monitor」ダッシュボードが表示

 curl localhost:9090/-/healthy が Prometheus is Healthy.

 pytest & CI ジョブ all green

 README / .env.example 更新

進め方
ディレクトリとファイルを作成

compose を書き換え、ローカルで docker compose up --build を確認

テスト追加（任意）→ pytest

git add → git commit -m "feat: add Prometheus & Grafana stack (D7)"

git push -u origin d7-monitor-stack → PR → Actions green

不明点やエラーが出たら随時知らせてください。

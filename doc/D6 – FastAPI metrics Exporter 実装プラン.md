D6 – FastAPI /metrics Exporter 実装プラン

curl http://localhost:8000/metrics で Prometheus 形式メトリクスを返し、pytest も green。
（後続タスク D7 で Prometheus + Grafana を compose に載せるための前提）

1. ディレクトリ & ファイル構成
bash


rakuten-monitor/
└─ app/
   ├─ __init__.py            # 既存ならそのまま
   ├─ metrics.py             # ← ビジネスロジックだけ残す／新規でも可
   └─ server.py              # ★ FastAPI アプリ本体
tests/
└─ test_metrics.py           # ★ 新ユニットテスト
docker-compose.yml           # app サービスに port 8000 公開を追記
2. app/server.py（サンプル実装）
python


from fastapi import FastAPI, Response, status
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ──────────────────────────────────────────────
# PROMETHEUS METRICS
registry = CollectorRegistry(auto_describe=True)

REQ_COUNTER = Counter(
    "rakuten_requests_total", "Total HTTP requests handled", registry=registry
)
ITEM_GAUGE = Gauge(
    "rakuten_available_items",
    "Current number of tracked items available",
    registry=registry,
)
# 初期値 0
ITEM_GAUGE.set(0)

# ──────────────────────────────────────────────
# FASTAPI
app = FastAPI(title="Rakuten Monitor API", version="0.1.0")


@app.on_event("startup")
def _startup_populate():
    # TODO: item count を DB から取得し ITEM_GAUGE.set(n)
    pass


@app.get("/healthz", status_code=status.HTTP_200_OK)
def healthz() -> dict[str, str]:
    """コンテナ用ヘルスチェック."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus 互換エンドポイント."""
    REQ_COUNTER.inc()
    payload = generate_latest(registry)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
ポイント

依存モジュール：prometheus-client, fastapi, uvicorn[standard] を requirements.txt へ追加

アプリ起動：開発時は uvicorn app.server:app --reload --port 8000
Docker 本番は gunicorn -k uvicorn.workers.UvicornWorker app.server:app

3. tests/test_metrics.py（同期テストで OK）
python


import requests
from subprocess import Popen
from time import sleep

def test_metrics_endpoint(tmp_path):
    # 開発用 uvicorn サーバを fork
    proc = Popen(
        ["uvicorn", "app.server:app", "--port", "8001", "--log-level", "error"]
    )
    try:
        # 起動待ち
        sleep(1)
        resp = requests.get("http://localhost:8001/metrics")
        assert resp.status_code == 200
        assert "rakuten_requests_total" in resp.text
    finally:
        proc.terminate()
        proc.wait()
pytest で 1 〜 2 秒増えるだけ

Windows の CI で Popen がうまく動かない場合は asyncio + httpx.AsyncClient 方式でも可

4. docker-compose.yml 変更点（抜粋）
yaml


services:
  app:
    build: .
    command: gunicorn -k uvicorn.workers.UvicornWorker app.server:app
    ports:
      - "8000:8000"       # ← 公開
    environment:
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
      # 追加があればここに
    healthcheck:
      test: ["CMD", "curl", "-fs", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
5. requirements.txt 追記


fastapi~=0.111
uvicorn[standard]~=0.30
prometheus-client~=0.20
6. README 追記（開発者ガイド）
md


### 開発用サーバ

```bash
uvicorn app.server:app --reload --port 8000
curl http://localhost:8000/metrics
yaml



---

## 7. CI 影響

| ジョブ | 追加調整 |
|--------|----------|
| **unit** | `pip install -r requirements.txt` で新依存が入るため追加作業不要 |
| **bdd** | 今回は影響なし（ステップ未実装のまま） |
| **docker** | build が FastAPI 依存をまとめてキャッシュするので若干時間アップ |

---

## 8. 完了判定

1. `pytest -q` → **all green**（テスト総数 +1）
2. `curl :8000/metrics` で 200 & Prometheus フォーマット
3. `docker compose up` で app コンテナ healthy
4. CI 4 ジョブ + check-secrets → success

---

### 次アクション

1. 上記サンプルをベースに **server.py / tests / compose** を実装
2. `pytest` & `docker compose up` で動作確認
3. コミット
   ```bash
   git add app/server.py tests/test_metrics.py docker-compose.yml requirements.txt README.md
   git commit -m "feat: add FastAPI /metrics exporter (D6)"
   git push -u origin d6-metrics
PR → Actions green を確認

作業中の不明点・エラーは遠慮なくお知らせください。

# Chaos テスト ガイド

## 概要
Chaos テストは、楽天商品監視ツールの例外処理と障害通知の堅牢性を検証します。
BDD シナリオ 6-8 に対応し、システムの障害耐性を確保します。

## テスト対象シナリオ

### シナリオ 6: レイアウト変更検出
**Given**: 楽天市場のページ構造が変更される  
**When**: 商品情報の抽出が失敗する  
**Then**: 
- `LayoutChangeError` が発生
- Discord に警告レベルの通知（黄色のEmbed）
- Prometheus に `monitor_fail_total{type="layout"}` メトリクス送信

### シナリオ 7: データベース接続障害
**Given**: PostgreSQL データベースが利用不可  
**When**: データベースアクセスが失敗する  
**Then**: 
- `DatabaseConnectionError` が発生
- Discord に重大エラー通知（赤色のEmbed）
- Prometheus に `monitor_fail_total{type="db"}` メトリクス送信

### シナリオ 8: Discord 通知システム障害
**Given**: Discord Webhook が利用不可  
**When**: 通知送信が複数回失敗する  
**Then**: 
- `DiscordNotificationError` が発生
- Prometheus に `monitor_fail_total{type="discord"}` メトリクス送信
- 大量失敗時は重大エラー警告を試行

## テスト実行方法

### 1. 単体テスト（推奨）
```bash
# 全Chaosテスト実行
pytest tests/test_monitor_chaos.py -v

# 特定シナリオのテスト
pytest tests/test_monitor_chaos.py::TestLayoutChangeDetection -v
pytest tests/test_monitor_chaos.py::TestDatabaseConnectionError -v
pytest tests/test_monitor_chaos.py::TestDiscordNotificationError -v
pytest tests/test_monitor_chaos.py::TestPrometheusIntegration -v

# 詳細出力
pytest tests/test_monitor_chaos.py -v -s --tb=long
```

### 2. 統合テスト（実環境）
```bash
# Chaos設定での実行（無効URL使用）
python3 -m monitor --config chaos_config.json

# 期待される出力:
# - NetworkError → Discord警告通知
# - LayoutChangeError → Discord警告通知 
# - DiscordNotificationError → ログ記録のみ
```

### 3. systemd 環境でのテスト
```bash
# テスト用の設定でサービス実行
sudo systemctl edit rakuten-monitor.service
# [Service]
# ExecStart=
# ExecStart=/usr/bin/python3 -m monitor --config chaos_config.json

# サービス再起動
sudo systemctl restart rakuten-monitor.service

# ログ確認
journalctl -u rakuten-monitor -f
```

## 期待されるテスト結果

### ✅ 成功パターン
1. **例外の適切な捕捉**: 各エラータイプが正しい例外クラスで処理される
2. **Discord通知送信**: エラーレベルに応じた適切な通知（警告/重大）
3. **Prometheusメトリクス**: 障害タイプ別のカウンタが増加
4. **ログ記録**: 適切なレベル（ERROR/CRITICAL）でログ出力
5. **エラー隔離**: 一つのシステム障害が他に波及しない

### ❌ 失敗パターンの対処
```bash
# テスト失敗時のデバッグ
pytest tests/test_monitor_chaos.py::test_layout_change_triggers_warning_notification -vs

# 実行ログの詳細確認
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from monitor import RakutenMonitor
monitor = RakutenMonitor('chaos_config.json')
try:
    monitor.run_monitoring()
except Exception as e:
    print(f'Expected error: {e}')
"
```

## モック vs 実環境テスト

### モックテスト（単体テスト）
- **利点**: 高速、決定的、依存関係なし
- **対象**: エラーハンドリングロジック、通知内容、メトリクス送信
- **実行**: `pytest tests/test_monitor_chaos.py`

### 実環境テスト（統合テスト）
- **利点**: 実際のネットワーク障害、タイムアウト、認証エラーを検証
- **対象**: 実際のHTTPエラー、DNS障害、証明書エラー
- **実行**: `python3 -m monitor --config chaos_config.json`

## Prometheus 統合テスト

### Pushgateway セットアップ
```bash
# Docker でテスト用 Pushgateway 起動
docker run -d --name test-pushgateway -p 9091:9091 prom/pushgateway

# 環境変数設定
export PROM_PUSHGATEWAY_URL=http://localhost:9091

# メトリクス送信テスト
python3 -c "
from prometheus_client import push_failure_metric
push_failure_metric('test', 'Chaos test metric')
print('✅ Prometheus test metric sent')
"

# メトリクス確認
curl http://localhost:9091/metrics | grep monitor_fail_total
```

### 期待されるメトリクス
```prometheus
# レイアウト変更エラー
monitor_fail_total{instance="localhost",type="layout"} 1

# データベース接続エラー
monitor_fail_total{instance="localhost",type="db"} 1

# Discord通知エラー
monitor_fail_total{instance="localhost",type="discord"} 3

# ネットワークエラー
monitor_fail_total{instance="localhost",type="network"} 2

# 監視実行メトリクス
monitor_items_processed_total{instance="localhost"} 4
monitor_changes_found_total{instance="localhost"} 0
monitor_duration_seconds{instance="localhost"} 12.34
```

## Discord 通知テスト

### テスト用 Webhook 設定
```bash
# 無効なWebhook URLでテスト
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/invalid/test"

# 実際のWebhookでテスト（開発環境のみ）
python3 -c "
from discord_notifier import DiscordNotifier
notifier = DiscordNotifier('$DISCORD_WEBHOOK_URL')
notifier.send_warning('Chaosテスト', 'これはテスト通知です。')
"
```

### 期待される Discord 通知
1. **警告通知（黄色）**: レイアウト変更、ネットワークエラー
2. **重大エラー（赤色）**: データベース障害、システム停止
3. **情報通知（青色）**: 接続テスト成功

## 継続的統合（CI）

### GitHub Actions 例
```yaml
name: Chaos Tests
on: [push, pull_request]
jobs:
  chaos-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      pushgateway:
        image: prom/pushgateway
        ports:
          - 9091:9091
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt pytest
      - name: Run Chaos Tests
        run: pytest tests/test_monitor_chaos.py -v
        env:
          PROM_PUSHGATEWAY_URL: http://localhost:9091
```

## トラブルシューティング

### よくある問題

#### 1. ImportError
```bash
# 相対インポートエラー
# 解決: PYTHONPATH設定
export PYTHONPATH=/home/yang_server/rakuten:$PYTHONPATH
pytest tests/test_monitor_chaos.py
```

#### 2. Mock設定エラー
```python
# patch対象の指定ミス
# ❌ @patch('discord_notifier.DiscordNotifier')
# ✅ @patch('monitor.DiscordNotifier')
```

#### 3. 非同期処理のテスト
```python
# 時間依存のテストを安定化
import time
from unittest.mock import patch

with patch('time.time', return_value=1234567890):
    # テスト実行
    pass
```

#### 4. ネットワークタイムアウト
```bash
# テスト用の短いタイムアウト設定
export NETWORK_TIMEOUT=5
python3 -m monitor --config chaos_config.json
```

## 本番環境での監視

### アラート設定例（Prometheus）
```yaml
groups:
  - name: rakuten-monitor-alerts
    rules:
      - alert: HighFailureRate
        expr: rate(monitor_fail_total[5m]) > 0.1
        for: 2m
        annotations:
          summary: "楽天監視ツールの失敗率が高い"
          
      - alert: DiscordSystemDown
        expr: monitor_fail_total{type="discord"} > 5
        for: 1m
        annotations:
          summary: "Discord通知システム障害"
          
      - alert: DatabaseConnectionFailed
        expr: monitor_fail_total{type="db"} > 0
        for: 0s
        annotations:
          summary: "データベース接続障害（即座に通知）"
```

### ログ監視（journalctl）
```bash
# エラーログ監視
journalctl -u rakuten-monitor -f --grep="ERROR|CRITICAL"

# 特定エラーの統計
journalctl -u rakuten-monitor --since="1 hour ago" | grep -c "LayoutChangeError"
journalctl -u rakuten-monitor --since="1 hour ago" | grep -c "DatabaseConnectionError"
```

## まとめ

Chaos テストにより以下が保証されます：

1. **障害隔離**: 一つのシステム障害が全体に波及しない
2. **適切な通知**: エラーレベルに応じた通知とエスカレーション
3. **可観測性**: メトリクスとログによる障害状況の把握
4. **復旧能力**: 部分的な障害からの自動復旧

これらのテストを定期的に実行することで、本番環境での障害耐性を維持できます。
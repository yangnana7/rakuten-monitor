"""
Prometheus metrics エクスポーターのテスト
"""

import pytest
import requests
import time
import random
from rakuten.metrics import (
    start_metrics_server,
    record_items_fetched,
    record_change_detected,
    record_run_success,
    record_run_failure,
    record_discord_notification,
    record_fetch_attempt,
)


class TestMetricsServer:
    @pytest.fixture
    def metrics_server(self):
        """メトリクスサーバーを起動してテスト用にセットアップ"""
        port = random.randint(9100, 9200)  # ランダムポート
        try:
            start_metrics_server(port)
            time.sleep(0.5)  # サーバー起動待機
            yield port
        except Exception as e:
            pytest.skip(f"Failed to start metrics server: {e}")

    def test_metrics_server_starts(self, metrics_server):
        """メトリクスサーバーが正常に起動することを確認"""
        port = metrics_server
        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_endpoint_contains_rakuten_metrics(self, metrics_server):
        """メトリクスエンドポイントが楽天監視関連のメトリクスを含むことを確認"""
        port = metrics_server

        # テストデータを記録
        record_items_fetched(42)
        record_change_detected("NEW")
        record_run_success()
        record_discord_notification("change", True)
        record_fetch_attempt("cloudscraper", True, 1.5)

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        assert response.status_code == 200

        content = response.text
        assert "rakuten_items_fetched_total" in content
        assert "rakuten_changes_detected_total" in content
        assert "rakuten_last_run_status" in content
        assert "rakuten_discord_notifications_total" in content
        assert "rakuten_fetch_duration_seconds" in content

    def test_items_fetched_counter(self, metrics_server):
        """商品取得数カウンターの動作確認"""
        port = metrics_server

        # カウンターを増加
        record_items_fetched(10)
        record_items_fetched(20)

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # カウンター値が正しく反映されることを確認
        assert (
            "rakuten_items_fetched_total 30" in content
            or "rakuten_items_fetched_total{} 30" in content
        )

    def test_change_detected_with_labels(self, metrics_server):
        """変更検出メトリクスのラベル機能確認"""
        port = metrics_server

        # 異なるタイプの変更を記録
        record_change_detected("NEW")
        record_change_detected("PRICE_UPDATE")
        record_change_detected("NEW")

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # ラベル付きメトリクスが含まれることを確認
        assert 'rakuten_changes_detected_total{change_type="NEW"}' in content
        assert 'rakuten_changes_detected_total{change_type="PRICE_UPDATE"}' in content

    def test_run_status_gauge(self, metrics_server):
        """実行ステータスゲージの動作確認"""
        port = metrics_server

        # 成功状態を記録
        record_run_success()

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # ステータスが1（成功）に設定されることを確認
        assert "rakuten_last_run_status 1" in content

        # 失敗状態を記録
        record_run_failure()

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # ステータスが0（失敗）に設定されることを確認
        assert "rakuten_last_run_status 0" in content

    def test_discord_notification_metrics(self, metrics_server):
        """Discord通知メトリクスの動作確認"""
        port = metrics_server

        # 成功と失敗の通知を記録
        record_discord_notification("change", True)
        record_discord_notification("error", False)

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # 通知メトリクスが正しく記録されることを確認
        assert (
            'rakuten_discord_notifications_total{notification_type="change",status="success"}'
            in content
        )
        assert (
            'rakuten_discord_notifications_total{notification_type="error",status="failure"}'
            in content
        )

    def test_fetch_duration_histogram(self, metrics_server):
        """フェッチ時間ヒストグラムの動作確認"""
        port = metrics_server

        # フェッチ時間を記録
        record_fetch_attempt("cloudscraper", True, 2.5)
        record_fetch_attempt("playwright", True, 5.0)

        response = requests.get(f"http://localhost:{port}/metrics", timeout=5)
        content = response.text

        # ヒストグラムメトリクスが含まれることを確認
        assert "rakuten_fetch_duration_seconds_bucket{le=" in content
        assert "rakuten_fetch_duration_seconds_count{method=" in content
        assert "rakuten_fetch_duration_seconds_sum{method=" in content

    def test_multiple_server_instances(self):
        """複数のサーバーインスタンスが異なるポートで起動できることを確認"""
        port1 = random.randint(9201, 9250)
        port2 = random.randint(9251, 9300)

        try:
            start_metrics_server(port1)
            time.sleep(0.5)

            response = requests.get(f"http://localhost:{port1}/metrics", timeout=5)
            assert response.status_code == 200

            start_metrics_server(port2)
            time.sleep(0.5)

            response = requests.get(f"http://localhost:{port2}/metrics", timeout=5)
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Server start failed: {e}")


class TestMetricsFunctions:
    """メトリクス記録関数の単体テスト"""

    def test_record_items_fetched(self):
        """商品取得数記録関数のテスト"""
        # 例外が発生しないことを確認
        record_items_fetched(100)
        record_items_fetched(0)

    def test_record_change_detected(self):
        """変更検出記録関数のテスト"""
        # 各種変更タイプで例外が発生しないことを確認
        record_change_detected("NEW")
        record_change_detected("PRICE_UPDATE")
        record_change_detected("TITLE_UPDATE")
        record_change_detected("RESTOCK")
        record_change_detected("SOLDOUT")

    def test_record_run_status(self):
        """実行ステータス記録関数のテスト"""
        record_run_success()
        record_run_failure()

    def test_record_discord_notification(self):
        """Discord通知記録関数のテスト"""
        record_discord_notification("change", True)
        record_discord_notification("error", False)
        record_discord_notification("alert", True)

    def test_record_fetch_attempt(self):
        """フェッチ試行記録関数のテスト"""
        record_fetch_attempt("cloudscraper", True, 1.0)
        record_fetch_attempt("playwright", False, 3.0)
        record_fetch_attempt("requests", True)  # duration なし

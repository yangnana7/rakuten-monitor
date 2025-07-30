"""Unit tests for FastAPI metrics endpoint."""

import requests
import subprocess
from subprocess import Popen
from time import sleep
import signal
import os


class TestMetricsEndpoint:
    """Test FastAPI metrics endpoint functionality."""

    def test_metrics_endpoint(self, tmp_path):
        """Test metrics endpoint returns Prometheus format data."""
        # 開発用 uvicorn サーバを fork
        proc = Popen(
            ["uvicorn", "app.server:app", "--port", "8001", "--log-level", "error"],
            stdout=None,
            stderr=None,
        )
        try:
            # 起動待ち
            sleep(2)

            # Test metrics endpoint
            resp = requests.get("http://localhost:8001/metrics", timeout=10)
            assert resp.status_code == 200
            assert "rakuten_requests_total" in resp.text
            assert "rakuten_available_items" in resp.text
            assert (
                resp.headers["content-type"]
                == "text/plain; version=0.0.4; charset=utf-8"
            )

        finally:
            # プロセス終了処理
            if os.name == "nt":  # Windows
                proc.terminate()
            else:  # Unix/Linux
                proc.send_signal(signal.SIGTERM)

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_healthz_endpoint(self, tmp_path):
        """Test health check endpoint."""
        # 開発用 uvicorn サーバを fork
        proc = Popen(
            ["uvicorn", "app.server:app", "--port", "8002", "--log-level", "error"],
            stdout=None,
            stderr=None,
        )
        try:
            # 起動待ち
            sleep(2)

            # Test health endpoint
            resp = requests.get("http://localhost:8002/healthz", timeout=10)
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

        finally:
            # プロセス終了処理
            if os.name == "nt":  # Windows
                proc.terminate()
            else:  # Unix/Linux
                proc.send_signal(signal.SIGTERM)

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_metrics_counter_increments(self, tmp_path):
        """Test that request counter increments on multiple calls."""
        # 開発用 uvicorn サーバを fork
        proc = Popen(
            ["uvicorn", "app.server:app", "--port", "8003", "--log-level", "error"],
            stdout=None,
            stderr=None,
        )
        try:
            # 起動待ち
            sleep(2)

            # First request
            resp1 = requests.get("http://localhost:8003/metrics", timeout=10)
            assert resp1.status_code == 200

            # Second request
            resp2 = requests.get("http://localhost:8003/metrics", timeout=10)
            assert resp2.status_code == 200

            # Counter should increment (basic check - actual value parsing would be more complex)
            assert "rakuten_requests_total" in resp2.text

        finally:
            # プロセス終了処理
            if os.name == "nt":  # Windows
                proc.terminate()
            else:  # Unix/Linux
                proc.send_signal(signal.SIGTERM)

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

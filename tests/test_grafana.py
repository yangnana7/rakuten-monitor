import requests
import time
import pytest


def test_grafana_health():
    """Test Grafana health endpoint"""
    time.sleep(5)  # コンテナ起動待ち (CI では compose up 前提)
    try:
        resp = requests.get("http://localhost:3000/api/health", timeout=10)
        resp.raise_for_status()
        health_data = resp.json()
        assert health_data["database"] == "ok"
    except requests.exceptions.RequestException:
        pytest.skip("Grafana not available (running without docker-compose)")


def test_prometheus_ready():
    """Test Prometheus ready endpoint"""
    time.sleep(5)  # コンテナ起動待ち
    try:
        resp = requests.get("http://localhost:9090/-/ready", timeout=10)
        resp.raise_for_status()
        assert "Prometheus is Ready" in resp.text
    except requests.exceptions.RequestException:
        pytest.skip("Prometheus not available (running without docker-compose)")

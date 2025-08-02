"""スケジューラモジュール - Phase4."""

import functools
import os
import time
from dotenv import load_dotenv

load_dotenv()


class Scheduler:
    def __init__(self):
        self.jobs = []

    def every(self, interval):
        return Job(self, interval)

    def run_pending(self):
        for job in self.jobs:
            if time.monotonic() - job.last_run >= job.interval:
                try:
                    job.fn()
                except Exception as e:
                    logger.exception("Job raised exception: %s", e)
                job.last_run = time.monotonic()


class Job:
    def __init__(self, scheduler, interval):
        self.scheduler = scheduler
        self.interval = interval
        self.fn = None
        self.last_run = time.monotonic()

    @property
    def seconds(self):
        return self

    def do(self, fn, *args, **kwargs):
        self.fn = functools.partial(fn, *args, **kwargs)
        self.scheduler.jobs.append(self)
        return self


_default = Scheduler()
every = _default.every
run_pending = _default.run_pending


try:
    import schedule
except ImportError:
    schedule = None

import logging  # noqa: E402
import importlib  # noqa: E402
from app.notifier.discord import DiscordClient  # noqa: E402
from app.core.error_handler import alert_on_exception  # noqa: E402

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Discord client for error alerts
_alert_client = DiscordClient(
    webhook_url=os.getenv(
        "ALERT_WEBHOOK_URL", "https://discord.com/api/webhooks/dummy"
    ),
    timeout=5.0,
)


@alert_on_exception(_alert_client, "#scheduler-alerts")
def start(interval=1, *, max_runs=None, runner=None):
    """
    スケジューラでmonitor.run_onceを指定秒間隔で実行。

    Args:
        interval: 実行間隔（秒）
        max_runs: 最大実行回数。Noneなら無限実行
        runner: 実行する関数。Noneの場合はapp.main.run_monitor_onceを使用
    """

    # 依存性注入: テスト時にmockを渡せるように
    if runner is None:
        monitor = importlib.import_module("app.main")
        runner = monitor.run_monitor_once

    def job():
        """監視ジョブの実行"""
        try:
            logger.info("Starting monitoring job...")
            notification_count = runner()
            logger.info(
                f"Monitoring job completed. Notifications sent: {notification_count}"
            )
        except Exception as e:
            logger.error(f"Monitoring job failed: {e}")
            # 例外が発生してもスケジューラは継続

    # 軽量スケジューラを使用
    scheduler = Scheduler()
    scheduler.every(0).seconds.do(job)  # Job runs every time run_pending() is called

    logger.info(f"Scheduler started with interval: {interval} seconds")

    runs = 0
    try:
        while True:
            scheduler.run_pending()
            if max_runs is not None and runs >= max_runs:
                logger.info(f"Scheduler completed {max_runs} runs")
                break
            time.sleep(interval)
            runs += 1
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user interrupt")
        raise
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        raise

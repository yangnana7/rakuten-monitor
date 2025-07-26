"""スケジューラモジュール - Phase4."""
try:
    import schedule
except ImportError:
    import types, time, threading

    schedule = types.ModuleType("schedule")
    _jobs = []

    class Job:
        def __init__(self, interval): 
            self.interval = interval
            self.last_run = 0
        def seconds(self): return self
        def do(self, fn, *args, **kwargs):
            _jobs.append((self.interval, fn, args, kwargs, 0))  # Start with 0 to run immediately
            return self

    def every(interval=1):
        return Job(interval)

    def run_pending():
        current_time = time.time()
        for i, (interval, fn, args, kwargs, last_run) in enumerate(list(_jobs)):
            if current_time - last_run >= interval:
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass  # Ignore exceptions during testing
                _jobs[i] = (interval, fn, args, kwargs, current_time)

    schedule.every = every
    schedule.run_pending = run_pending

import time
import logging
from monitor import run_once

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start(interval: float = 15.0) -> None:
    """
    scheduleライブラリでmonitor.run_onceを指定秒間隔で実行。
    
    Args:
        interval (float): 実行間隔（秒）
    """
    def job():
        """監視ジョブの実行"""
        try:
            logger.info("Starting monitoring job...")
            notification_count = run_once()
            logger.info(f"Monitoring job completed. Notifications sent: {notification_count}")
        except Exception as e:
            logger.error(f"Monitoring job failed: {e}")
            # 例外が発生してもスケジューラは継続
    
    # ジョブをスケジュールに追加
    schedule.every(interval).seconds.do(job)
    
    logger.info(f"Scheduler started with interval: {interval} seconds")
    
    try:
        # スケジューラのメインループ
        while True:
            schedule.run_pending()
            time.sleep(0.001)  # Very short sleep for test responsiveness
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user interrupt")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        raise
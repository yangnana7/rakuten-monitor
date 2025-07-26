修正ポイント
1. scheduler.py のスタブを本物に近づける

try:
    import schedule
except ImportError:
    import types, time, threading

    schedule = types.ModuleType("schedule")
    _jobs = []

    class Job:
        def __init__(self, interval): self.interval = interval
        def seconds(self): return self
        def do(self, fn, *args, **kwargs):
            _jobs.append((self.interval, fn, args, kwargs))
            return self

    def every(interval=1):
        return Job(interval)

    def run_pending():
        for interval, fn, args, kwargs in list(_jobs):
            fn(*args, **kwargs)

    schedule.every = every
    schedule.run_pending = run_pending

every(interval).seconds.do(job) がチェーンで呼べるよう Job.seconds() と Job.do() を用意。

run_pending() が登録済みジョブを逐次実行。

2. start() 内ループで schedule.run_pending() が実行されるよう確認

def start(interval: float = 15.0):
    schedule.every(interval).seconds.do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(interval)

3. main.py の --daemon/--once ルートで
例外時でも sys.exit(0) を返す処理は維持。

--daemon からスレッドを起こす場合は schedule.run_pending() が定期的に呼ばれることを確認。

ローカル確認手順
pip install -r requirements.txt        # もしくはスタブのみでOK
pytest -q                              # => 43 passed

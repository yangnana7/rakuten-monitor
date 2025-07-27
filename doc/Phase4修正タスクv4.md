[Goal] tests/test_scheduler.py をすべて通す。

1. scheduler.py に軽量 stub を実装:
   - class Scheduler:
       def __init__(self): self.jobs = []
       def every(self, interval): return Job(self, interval)
       def run_pending(self): [job.run() for job in list(self.jobs)]
   - class Job:
       def __init__(self, scheduler, interval): ...
       @property
       def seconds(self): return self  # chainable
       def do(self, fn, *args, **kw):
           self.fn = functools.partial(fn, *args, **kw)
           self.scheduler.jobs.append(self)
           return self
       def run(self): self.fn()

2. scheduler モジュールレベルに
   ```python
   _default = Scheduler()
   every = _default.every
   run_pending = _default.run_pending

"""Opt-in telemetry for the finite synthetic Q2 child; never a timeout policy."""
import faulthandler
import json
import os
import threading
import time


class Diagnostics:
    def __init__(self, delay=170):
        # Duplicate before pytest starts per-test capture. Only numbers, phase
        # labels and Python stack locations are emitted, never locals or inputs.
        self.stream = os.fdopen(os.dup(2), "w", buffering=1)
        self.started = time.monotonic()
        self.cpu = time.process_time()
        self.active = None
        self.count = 0
        self.lock = threading.Lock()
        self.timer = threading.Timer(delay, self.snapshot)
        self.timer.daemon = True
        self.timer.start()

    def emit(self, event, **fields):
        self.stream.write("Q2_DIAGNOSTIC " + json.dumps({
            "event": event, "wall_s": round(time.monotonic() - self.started, 6),
            "process_cpu_s": round(time.process_time() - self.cpu, 6), **fields,
        }) + "\n")
        self.stream.flush()

    def pytest_runtest_logstart(self, nodeid, location):
        with self.lock:
            self.count += 1
            self.active = (self.count, time.monotonic())
            self.emit("start", case=self.count)

    def pytest_runtest_logreport(self, report):
        with self.lock:
            self.emit("phase", case=self.count, phase=report.when,
                      outcome=report.outcome, duration_s=round(report.duration, 6))

    def pytest_runtest_logfinish(self, nodeid, location):
        with self.lock:
            self.emit("finish", case=self.count,
                      elapsed_s=round(time.monotonic() - self.active[1], 6))
            self.active = None

    def snapshot(self):
        with self.lock:
            self.emit("pre_deadline", active_case=self.active[0] if self.active else None,
                      active_elapsed_s=round(time.monotonic() - self.active[1], 6) if self.active else None)
            faulthandler.dump_traceback(file=self.stream, all_threads=True)

    def pytest_sessionfinish(self, session, exitstatus):
        self.timer.cancel()
        # No join. An active snapshot can briefly hold this lock; the parent
        # still enforces its unchanged subprocess deadline.
        with self.lock:
            self.emit("end", exit=int(exitstatus))
        # Keep fd valid until process exit if the timer was already scheduled.

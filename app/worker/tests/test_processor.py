"""WRK-RUN-03/05: hard processing deadline and termination grace."""

import subprocess
from threading import Event
import pytest
from worker import processor


@pytest.mark.parametrize("stopping,maximum", [(False, 120), (True, 60)])
def test_wrk_run_deadline_kills_stuck_child(monkeypatch, stopping, maximum):
    elapsed = [0]

    class StuckChild:
        killed = False
        returncode = None

        def communicate(self, input=None, timeout=None):
            if self.killed:
                return b"", b""
            elapsed[0] += timeout
            raise subprocess.TimeoutExpired("synthetic", timeout)

        def poll(self):
            return None if not self.killed else -9

        def kill(self):
            self.killed = True

    child = StuckChild()
    monkeypatch.setattr(processor.subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(processor.time, "monotonic", lambda: elapsed[0])
    shutdown = Event()
    if stopping:
        shutdown.set()
    with pytest.raises(TimeoutError):
        processor.process_document(b"synthetic", "image/png", "id", shutdown)
    assert child.killed
    assert elapsed[0] == maximum

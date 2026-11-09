"""OCR subprocess limits work to 120 s, or 60 s after shutdown is requested."""

import json
import subprocess
import sys
import time
from typing import Any
from threading import Event


def process_document(
    content: bytes, mime: str, document_id: str, shutdown: Event | None = None
) -> dict[str, Any]:
    process = subprocess.Popen(
        [sys.executable, "-m", "worker.ocr_job", mime, document_id],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 120
    first = True
    try:
        while True:
            if shutdown is not None and shutdown.is_set():
                deadline = min(deadline, time.monotonic() + 60)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("WORKER_TIMEOUT")
            try:
                output, _ = process.communicate(
                    input=content if first else None, timeout=min(1, remaining)
                )
                if process.returncode:
                    raise RuntimeError("WORKER_ERROR")
                return json.loads(output)
            except subprocess.TimeoutExpired:
                first = False
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

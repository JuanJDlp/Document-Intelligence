import copy
import json
import logging
import os
import signal
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any, Callable
from .processor import process_document
from .store import JobStore, OversizeDocument, TERMINAL, stamp

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        store: JobStore,
        *,
        processor: Callable[..., dict[str, Any]] = process_document,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        lease_seconds: int = 300,
        max_attempts: int = 3,
        max_bytes: int = 5242880,
    ) -> None:
        self.store, self.processor = store, processor
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep, self.lease_seconds, self.max_attempts, self.max_bytes = (
            sleep,
            lease_seconds,
            max_attempts,
            max_bytes,
        )
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"
        self.shutdown = threading.Event()

    def claim(self, job: dict[str, Any]) -> dict[str, Any] | None:
        time = self.clock()
        if job["status"] in TERMINAL or job["available_at"] > stamp(time):
            return None
        if int(job["attempts"]) >= int(job.get("max_attempts", self.max_attempts)):
            final = dict(
                job, status="FAILED", last_error_code="WORKER_LEASE_EXPIRED", updated_at=stamp(time)
            )
            final.pop("lease_owner", None)
            if self.store.transition(job, final, time):
                self.notify(final)
            return None
        new = dict(
            job,
            status="RUNNING",
            lease_owner=self.worker_id,
            attempts=int(job["attempts"]) + 1,
            available_at=stamp(time + timedelta(seconds=self.lease_seconds)),
            claimed_at=stamp(time),
            updated_at=stamp(time),
        )
        return new if self.store.transition(job, new, time) else None

    def notify(self, job: dict[str, Any]) -> None:
        state = "FAILED"
        for attempt in range(3):
            try:
                self.store.publish(job, self.clock())
                state = "SENT"
                break
            except Exception as exc:
                logger.warning(
                    "event=notification.failed job_id=%s exception_class=%s",
                    job["job_id"],
                    type(exc).__name__,
                )
                if attempt < 2:
                    self.sleep(attempt + 1)
        # A metadata write failure must not cause another publication.
        self.store.record_notification(job, state, self.clock())

    def finish(
        self,
        job: dict[str, Any],
        *,
        result: dict[str, Any] | None = None,
        code: str | None = None,
        retryable: bool = False,
    ) -> bool:
        time = self.clock()
        final = dict(job, updated_at=stamp(time))
        if retryable and int(job["attempts"]) < int(job.get("max_attempts", self.max_attempts)):
            final.update(
                status="PENDING",
                available_at=stamp(time + timedelta(seconds=30 * 2 ** (int(job["attempts"]) - 1))),
            )
        else:
            final["status"] = {"completed": "COMPLETED", "partial": "PARTIAL"}.get(
                str((result or {}).get("status")), "FAILED"
            )
        final.pop("lease_owner", None)
        if code:
            final["last_error_code"] = code
        else:
            final.pop("last_error_code", None)
        if result is not None and final["status"] in TERMINAL:
            safe = copy.deepcopy(result)
            safe.pop("raw_text", None)
            safe.get("validation", {}).pop("field_sources", None)
            if len(json.dumps(safe).encode()) > 100000:
                safe["extracted_data"]["line_items"] = safe["extracted_data"]["line_items"][:50]
                safe["validation"]["warnings"].append(
                    {
                        "code": "LINE_ITEMS_TRUNCATED",
                        "field": "line_items",
                        "message": "Line items truncated.",
                    }
                )
            if len(json.dumps(safe).encode()) > 100000:
                final.update(status="FAILED", last_error_code="WORKER_RESULT_TOO_LARGE")
            else:
                final["result"] = safe
        if self.store.transition(job, final, time, require_live=True):
            logger.info(
                "event=job.finished document_id=%s job_id=%s status=%s",
                job["document_id"],
                job["job_id"],
                final["status"],
            )
            if final["status"] in TERMINAL:
                self.notify(final)
            return True
        logger.info("event=lease_lost job_id=%s", job["job_id"])
        return False

    def process_one(self, candidate: dict[str, Any]) -> bool:
        job = self.claim(candidate)
        if job is None:
            return False
        try:
            document = self.store.document(job["document_id"])
            if document is None:
                return self.finish(job, code="DOCUMENT_NOT_FOUND")
            content = self.store.read_bytes(document["s3_key"], self.max_bytes)
            result = self.processor(
                content, document["mime_type"], document["document_id"], self.shutdown
            )
            error = result.get("error") or {}
            return self.finish(
                job, result=result, code=error.get("code"), retryable=error.get("retryable", False)
            )
        except OversizeDocument:
            return self.finish(job, code="INVALID_DOCUMENT")
        except TimeoutError:
            return self.finish(job, code="WORKER_TIMEOUT", retryable=True)
        except Exception as exc:
            logger.error(
                "event=job.error job_id=%s exception_class=%s", job["job_id"], type(exc).__name__
            )
            return self.finish(job, code="WORKER_ERROR", retryable=True)

    def run_once(self) -> bool:
        candidates = self.store.poll(self.clock())
        for job in candidates:
            if self.shutdown.is_set():
                break
            self.process_one(job)
        return bool(candidates)

    def run(self) -> None:
        while not self.shutdown.is_set():
            try:
                busy = self.run_once()
            except Exception as exc:
                logger.error("event=poll.failed exception_class=%s", type(exc).__name__)
                busy = False
            self.shutdown.wait(5 if busy else 15)


def from_environment() -> Worker:
    names = ("UPLOADS_BUCKET", "DOCUMENTS_TABLE", "JOBS_TABLE", "PROCESSING_TOPIC_ARN")
    for name in names:
        if not os.environ.get("DOCUPROCESS_" + name):
            raise RuntimeError("Missing configuration: DOCUPROCESS_" + name)
    env = os.environ
    store = JobStore(
        region=env.get("DOCUPROCESS_AWS_REGION", "us-east-1"),
        bucket=env["DOCUPROCESS_UPLOADS_BUCKET"],
        documents=env["DOCUPROCESS_DOCUMENTS_TABLE"],
        jobs=env["DOCUPROCESS_JOBS_TABLE"],
        topic=env["DOCUPROCESS_PROCESSING_TOPIC_ARN"],
    )
    return Worker(
        store,
        lease_seconds=int(env.get("DOCUPROCESS_LEASE_SECONDS", "300")),
        max_attempts=int(env.get("DOCUPROCESS_MAX_ATTEMPTS", "3")),
        max_bytes=int(env.get("DOCUPROCESS_MAX_UPLOAD_BYTES", "5242880")),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = from_environment()
    signal.signal(signal.SIGTERM, lambda *_: worker.shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: worker.shutdown.set())
    worker.run()

import copy
from datetime import timedelta
import json
from worker.main import Worker
from worker.store import stamp


def pending(services, content):
    created = services.docs.create("synthetic-user", "receipt.png", "image/png", content)
    job = services.store.jobs.get_item(Key={"job_id": created["job_id"]})["Item"]
    return created, job


def test_wrk_clm_racing_claims(aws_services, image_bytes):
    _, job = pending(aws_services, image_bytes)
    aws_services.worker.clock = lambda: __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    assert aws_services.worker.claim(job)
    assert aws_services.worker.claim(job) is None


def test_wrk_per_stale_worker_fenced(aws_services, image_bytes, clock):
    created, job = pending(aws_services, image_bytes)
    from datetime import datetime, timezone

    clock.time = datetime.now(timezone.utc)
    old = aws_services.worker.claim(job)
    clock.time += timedelta(seconds=301)
    competitor = Worker(aws_services.store, clock=clock, sleep=lambda _: None)
    current = competitor.claim(old)
    assert current
    assert aws_services.worker.finish(old, code="WORKER_ERROR") is False
    document = aws_services.store.document(created["document_id"])
    assert document["processing_status"] == "RUNNING"
    assert document["processing_attempts"] == 2
    assert aws_services.messages == []


def test_wrk_retry_backoff_and_exhaustion(aws_services, image_bytes, clock):
    from datetime import datetime, timezone

    clock.time = datetime.now(timezone.utc)
    _, job = pending(aws_services, image_bytes)
    claimed = aws_services.worker.claim(job)
    assert aws_services.worker.finish(claimed, code="WORKER_TIMEOUT", retryable=True)
    retried = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert retried["status"] == "PENDING"
    assert retried["available_at"] == stamp(clock.time + timedelta(seconds=30))
    assert aws_services.messages == []
    for attempt in (2, 3):
        clock.time += timedelta(seconds=61)
        claimed = aws_services.worker.claim(retried)
        assert claimed["attempts"] == attempt
        aws_services.worker.finish(claimed, code="WORKER_TIMEOUT", retryable=True)
        retried = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert retried["status"] == "FAILED"
    assert len(aws_services.messages) == 1


def test_wrk_expired_final_attempt(aws_services, image_bytes, clock):
    from datetime import datetime, timezone

    clock.time = datetime.now(timezone.utc)
    _, job = pending(aws_services, image_bytes)
    job["attempts"] = 2
    aws_services.store.jobs.put_item(Item=job)
    claimed = aws_services.worker.claim(job)
    clock.time += timedelta(seconds=301)
    assert aws_services.worker.claim(claimed) is None
    assert (
        aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]["status"]
        == "FAILED"
    )


def test_wrk_not_sns_failure(aws_services, image_bytes, clock, monkeypatch):
    from datetime import datetime, timezone

    clock.time = datetime.now(timezone.utc)
    _, job = pending(aws_services, image_bytes)
    calls = []

    def fail(*args):
        calls.append(1)
        raise RuntimeError("private payload must not be logged")

    monkeypatch.setattr(aws_services.store, "publish", fail)
    assert aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["notification_status"] == "FAILED"
    assert final["status"] == "COMPLETED"
    assert len(calls) == 3
    assert aws_services.worker.claim(final) is None


def test_dat_acc_sparse_jobs_invisible(aws_services, clock):
    aws_services.store.jobs.put_item(Item={"job_id": "synthetic-sparse", "attempts": 0})
    assert aws_services.store.poll(clock.time) == []


def test_wrk_per_no_raw_text(aws_services, image_bytes, clock):
    from datetime import datetime, timezone

    clock.time = datetime.now(timezone.utc)
    created, job = pending(aws_services, image_bytes)
    original = aws_services.worker.processor

    def debug(*args):
        result = copy.deepcopy(original(*args))
        result["raw_text"] = "private raw"
        result["validation"]["field_sources"] = {"total": "private"}
        return result

    aws_services.worker.processor = debug
    assert aws_services.worker.process_one(job)
    result = aws_services.store.document(created["document_id"])["result"]
    assert "raw_text" not in result
    assert "field_sources" not in result["validation"]
    message = json.loads(aws_services.messages[0]["Message"])
    assert set(message) == {"event", "document_id", "job_id", "status", "occurred_at"}

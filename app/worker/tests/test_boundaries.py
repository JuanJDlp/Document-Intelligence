"""WRK-PER, WRK-NOT, WRK-ERR: resource and terminal consistency boundaries."""

import copy
from worker.store import OversizeDocument
from test_worker import pending


def test_wrk_clm_expired_lease_cannot_finish_without_competitor(aws_services, image_bytes, clock):
    from datetime import timedelta

    _, job = pending(aws_services, image_bytes)
    claimed = aws_services.worker.claim(job)
    clock.time += timedelta(seconds=301)
    assert aws_services.worker.finish(claimed, code="WORKER_ERROR") is False
    assert not aws_services.messages


def test_wrk_err_missing_document_is_terminal(aws_services, image_bytes):
    created, job = pending(aws_services, image_bytes)
    aws_services.store.documents.delete_item(Key={"document_id": created["document_id"]})
    assert aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["status"] == "FAILED"
    assert final["last_error_code"] == "DOCUMENT_NOT_FOUND"


def test_wrk_err_oversize_is_permanent(aws_services, image_bytes, monkeypatch):
    _, job = pending(aws_services, image_bytes)

    def reject(*args):
        raise OversizeDocument()

    monkeypatch.setattr(aws_services.store, "read_bytes", reject)
    assert aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["status"] == "FAILED"
    assert final["attempts"] == 1
    assert final["last_error_code"] == "INVALID_DOCUMENT"


def test_wrk_not_metadata_failure_does_not_republish(aws_services, image_bytes, monkeypatch):
    _, job = pending(aws_services, image_bytes)

    def reject(*args):
        raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(aws_services.store, "record_notification", reject)
    aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["status"] == "COMPLETED"
    assert len(aws_services.messages) == 1
    assert aws_services.worker.claim(final) is None


def test_wrk_per_result_size_guard(aws_services, image_bytes):
    created, job = pending(aws_services, image_bytes)
    original = aws_services.worker.processor

    def large(*args):
        result = copy.deepcopy(original(*args))
        result["extracted_data"]["merchant_name"] = "X" * 100001
        return result

    aws_services.worker.processor = large
    assert aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["status"] == "FAILED"
    assert final["last_error_code"] == "WORKER_RESULT_TOO_LARGE"
    assert "result" not in aws_services.store.document(created["document_id"])


def test_wrk_not_failure_has_no_sent_timestamp(aws_services, image_bytes, monkeypatch):
    _, job = pending(aws_services, image_bytes)

    def reject(*args):
        raise RuntimeError("synthetic publish failure")

    monkeypatch.setattr(aws_services.store, "publish", reject)
    assert aws_services.worker.process_one(job)
    final = aws_services.store.jobs.get_item(Key={"job_id": job["job_id"]})["Item"]
    assert final["notification_status"] == "FAILED"
    assert "notified_at" not in final

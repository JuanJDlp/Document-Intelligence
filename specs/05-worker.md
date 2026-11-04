# 05 — Worker

Implementation: `app/worker/`. It is a long-running Python process started by systemd on every instance of the Auto Scaling Group, next to the API.

The worker is the **only** component that calls the Receipt Extraction Engine, and the only one that writes processing results.

## 1. Responsibilities

1. Poll the `jobs` table for claimable jobs.
2. Claim one job safely (lease-based, conditional writes).
3. Load the document's object from S3.
4. Invoke the engine (`ENG-API-*`) with the bytes and metadata.
5. Persist the result and the job state in DynamoDB.
6. Publish a notification to SNS on terminal states.

It does **not** serve HTTP, manage users, or change the engine's logic.

## 2. Job state machine

```
            claim                 engine ok (completed)      -> COMPLETED
PENDING ─────────────► RUNNING ── engine ok (partial)        -> PARTIAL
   ▲                    │  │   ── engine failed, permanent  -> FAILED
   │   retryable error  │  └── engine failed, retryable AND attempts < max_attempts
   └────────────────────┘        (backoff, back to PENDING)
                         lease expired AND attempts >= max_attempts -> FAILED
```

- **WRK-STM-01** (active) Allowed statuses: `PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`. No other values are stored.
- **WRK-STM-02** (active) Terminal statuses: `COMPLETED`, `PARTIAL`, `FAILED`. Terminal jobs are never claimed again.
- **WRK-STM-03** (active) Every status transition is a conditional write that checks the expected current status and, for `RUNNING`, the `lease_owner` value. A lost race must not corrupt state.

## 3. Claiming

- **WRK-CLM-01** (active) Polling query: GSI `gsi_status_available` with partition key `status` and sort key `available_at`. Two queries per poll: `status = PENDING` and `available_at <= now`; `status = RUNNING` and `available_at <= now` (expired leases). Limit 10 each.
- **WRK-CLM-02** (active) Claim is a single `UpdateItem` with condition:
  - for `PENDING`: `status = :pending AND available_at <= :now`;
  - for an expired lease: `status = :running AND available_at <= :now`.
  On success it sets `status = RUNNING`, `lease_owner = <worker_id>`, `attempts = attempts + 1`, `available_at = now + lease_seconds`, `claimed_at = now`, `updated_at = now`.
- **WRK-CLM-03** (active) If the conditional write fails, the worker moves on to the next candidate. No retry loop on the same item.
- **WRK-CLM-04** (active) `lease_seconds` default `300`. The engine's total processing time MUST stay below the lease. Enforced by a per-job deadline of `120` seconds (`WRK-PRC-03`).
- **WRK-CLM-05** (active) An expired lease with `attempts >= max_attempts` is not reclaimed. The worker marks it `FAILED` with `last_error_code = WORKER_LEASE_EXPIRED`. This is done by the same worker that finds it, using a conditional write.
- **WRK-CLM-06** (active) `max_attempts` default `3`.

## 4. Processing

- **WRK-PRC-01** (active) The worker loads the `documents` item for the job's `document_id`. If it does not exist, the job is `FAILED` with `last_error_code = DOCUMENT_NOT_FOUND` (permanent).
- **WRK-PRC-02** (active) The worker reads the S3 object with a size guard: `head_object` first; if `ContentLength > max_upload_bytes`, the job is `FAILED` with `INVALID_DOCUMENT` (permanent). Otherwise `get_object` and read the bytes.
- **WRK-PRC-03** (active) The engine is called with a deadline of `120` seconds. A timeout is a retryable failure (`WORKER_TIMEOUT`).
- **WRK-PRC-04** (active) The engine receives a `DocumentInput` (`ENG-API-02`) built by the worker from the S3 bytes, the declared MIME type stored on the `documents` item, the filename, and the `document_id` for correlation. The worker never passes the S3 key, bucket name, or user identifier to the engine.
- **WRK-PRC-05** (active) Mapping engine results to job state:

  | Engine `status` | Engine `error.code` | `retryable` | Job result |
  |---|---|---|---|
  | `completed` | — | — | `COMPLETED` |
  | `partial` | — | — | `PARTIAL` |
  | `failed` | `OCR_FAILED` | `true` | retry if attempts left, else `FAILED` |
  | `failed` | any other | `false` | `FAILED` |

- **WRK-PRC-06** (active) Any unexpected exception in the worker (S3 error, DynamoDB throttling, bug) is treated as retryable with code `WORKER_ERROR`, up to `max_attempts`. Exceptions are logged with class name and job ID, never with document content.
- **WRK-PRC-07** (active) Retry backoff: `available_at = now + 30 s × 2^(attempts − 1)`. For attempts 1, 2, 3 that is 30 s, 60 s, 120 s.

## 5. Persistence

- **WRK-PER-01** (active) Order of writes for a finished job:
  1. Update `documents` item: `processing_status`, `result` (engine result without `raw_text`), `updated_at`.
  2. Conditionally update `jobs` item to the terminal status, with `lease_owner = <me>` and `status = RUNNING`.
- **WRK-PER-02** (active) If step 2's condition fails (lease was taken by another worker), the worker discards its result and logs `lease_lost` with the job ID. It does not publish a notification.
- **WRK-PER-03** (active) `documents.processing_status` mirrors the job status at all times so the API can read one item.
- **WRK-PER-04** (active) The engine result stored in DynamoDB MUST be under 100 KB. If it would exceed that, `line_items` is truncated to the first 50 items and a warning `LINE_ITEMS_TRUNCATED` is added.
- **WRK-PER-05** (active) Raw OCR text is never persisted by the worker (`ENG-OUT-04`).

## 6. Notifications

- **WRK-NOT-01** (active) After a terminal status is persisted, the worker publishes one SNS message to `docuprocess-sandbox-processing-events`.
- **WRK-NOT-02** (active) Message body (JSON string) contains only:
  ```json
  { "event": "document.processing.finished", "document_id": "…", "job_id": "…", "status": "COMPLETED", "occurred_at": "2026-11-03T21:04:05Z" }
  ```
  It MUST NOT contain filenames, extracted financial data, NIT, user email, or raw text. Message attribute `status` mirrors `status` for filtering.
- **WRK-NOT-03** (active) SNS publish is attempted 3 times with backoff (1 s, 2 s). If all fail, the job record gets `notification_status = "FAILED"` and a log line is emitted. The job is still terminal. Automatic re-notification is out of scope for version 1 (documented limitation).
- **WRK-NOT-04** (active) On success, `notification_status = "SENT"` and `notified_at` is set on the `jobs` item.

## 7. Runtime behavior

- **WRK-RUN-01** (active) Poll interval: 5 s when the last poll found work; 15 s when idle; back to 5 s after work.
- **WRK-RUN-02** (active) One job at a time per worker process. Horizontal scale comes from the ASG (`INF-ASG-*`) and from running on every instance.
- **WRK-RUN-03** (active) On `SIGTERM` the worker stops claiming new jobs, finishes the current job if it can within 60 s, and exits `0`. systemd `TimeoutStopSec=90`.
- **WRK-RUN-04** (active) Worker ID: `<hostname>-<pid>-<random 6 chars>`. Unique per process, logged at startup.
- **WRK-RUN-05** (active) Startup fails fast if required configuration is missing (names only, never values).

## 8. Configuration

| Variable | Default | Notes |
|---|---|---|
| `DOCUPROCESS_DB_*` | — | Only if the worker touches RDS (it does not in v1; see `WRK-SCOPE-01`) |
| `DOCUPROCESS_AWS_REGION` | `us-east-1` | |
| `DOCUPROCESS_UPLOADS_BUCKET` | — | required |
| `DOCUPROCESS_DOCUMENTS_TABLE` | — | required |
| `DOCUPROCESS_JOBS_TABLE` | — | required |
| `DOCUPROCESS_PROCESSING_TOPIC_ARN` | — | required |
| `DOCUPROCESS_MAX_UPLOAD_BYTES` | `5242880` | |
| `DOCUPROCESS_OCR_PROVIDER` | `tesseract` | Only `tesseract` in v1 (`ADR-012`) |
| `DOCUPROCESS_MAX_ATTEMPTS` | `3` | |
| `DOCUPROCESS_LEASE_SECONDS` | `300` | |

- **WRK-SCOPE-01** (active) The worker does **not** connect to RDS in version 1. Users and sessions are API concerns only. The worker's DB variables are therefore not required.

## 9. Module layout (`app/worker/src/worker/`)

- `main.py` — entry point, signal handling, poll loop.
- `config.py` — typed settings.
- `jobs_repository.py` — DynamoDB claim, lease, status updates (conditional writes).
- `documents_repository.py` — DynamoDB document reads and result writes.
- `storage.py` — S3 adapter that reads the uploaded object and builds the engine's `DocumentInput`.

- `notifier.py` — SNS adapter with retries.
- `processor.py` — orchestrates one job: load → engine → persist → notify.

Each adapter MUST be injectable so that `tests/` can replace it with `moto` or with fakes (`TST-UNIT-WRK-*`).

## 10. Acceptance

- **WRK-ACC-01** (active) Unit tests with `moto` (or in-memory fakes) cover: claim success, claim race lost, expired lease reclaim, `max_attempts` exhaustion, retryable vs permanent mapping, lease lost on persist, SNS retry and final failure.
- **WRK-ACC-02** (active) End-to-end in the sandbox: upload one sample receipt, the job reaches a terminal state within 2 minutes, and exactly one SNS message is published.

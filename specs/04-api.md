# 04 — REST API

Implementation: `app/api/` (FastAPI, Python 3.12, SQLAlchemy 2 with PyMySQL in production, SQLite in tests).

## 1. General conventions

- **API-GEN-01** (active) Base path `/api/v1`. All request and response bodies are JSON, except uploads (`multipart/form-data`).
- **API-GEN-02** (active) Identifiers are UUID v4 strings.
- **API-GEN-03** (active) Timestamps are UTC ISO 8601 with `Z` suffix (`2026-11-03T21:04:05Z`).
- **API-GEN-04** (active) Money values, when present, are strings with two decimals (see `ENG-NRM-01`). The API never converts them to numbers.
- **API-GEN-05** (active) Errors use one shape:
  ```json
  { "error": { "code": "DOCUMENT_TOO_LARGE", "message": "File exceeds 5 MB.", "details": {} } }
  ```
  `code` is a stable UPPER_SNAKE_CASE string. `message` is English and human-readable. `details` is an object, may be empty.
- **API-GEN-06** (active) Common error codes:

  | HTTP | code | When |
  |---|---|---|
  | 400 | `VALIDATION_ERROR` | Body or query fails schema validation |
  | 401 | `UNAUTHENTICATED` | Missing, invalid, expired, or revoked token |
  | 403 | `FORBIDDEN` | Authenticated but not allowed |
  | 404 | `NOT_FOUND` | Resource missing **or** not owned by caller (no existence leak) |
  | 409 | `CONFLICT` | Email already registered |
  | 413 | `DOCUMENT_TOO_LARGE` | Upload exceeds `max_upload_bytes` |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | Sniffed type is not PDF, PNG, or JPEG |
  | 422 | `INVALID_DOCUMENT` | Empty, corrupted, encrypted, or multi-page PDF |
  | 500 | `INTERNAL_ERROR` | Unexpected; never includes stack traces |

## 2. Authentication and sessions

- **API-AUTH-01** (active) `POST /api/v1/auth/register` — body `{ "email", "password", "full_name" }`. Returns `201` with the user (no password, no hash). Role defaults to `user`. Duplicate email → `409 CONFLICT`.
- **API-AUTH-02** (active) Email is normalized to lowercase and trimmed. Must match a simple RFC-like pattern (`^[^@\s]+@[^@\s]+\.[^@\s]+$`). Max length 254.
- **API-AUTH-03** (active) Password rules: 12 to 128 characters; at least one letter and one digit. Stored with Argon2id (`argon2-cffi` default parameters or stronger).
- **API-AUTH-04** (active) `POST /api/v1/auth/login` — body `{ "email", "password" }`. Success returns `200` `{ "token", "expires_at" }`. Wrong email or password returns `401 UNAUTHENTICATED` with the same message for both cases. The login path MUST run a password hash verification even when the email does not exist (timing equalization).
- **API-AUTH-05** (active) Session token: `secrets.token_urlsafe(32)`. Returned once. Stored in table `sessions` only as `SHA-256(token)` (`DAT-RDB-03`).
- **API-AUTH-06** (active) Session lifetime: 8 hours. `expires_at` is returned. No refresh tokens in version 1.
- **API-AUTH-07** (active) Clients send `Authorization: Bearer <token>`. Tokens are never accepted in query strings.
- **API-AUTH-08** (active) `POST /api/v1/auth/logout` — revokes the current session (sets `revoked_at`). Returns `204`.
- **API-AUTH-09** (active) `GET /api/v1/me` — returns the current user `{ "id", "email", "full_name", "role", "created_at" }`.

## 3. Documents

- **API-DOC-01** (active) `POST /api/v1/documents` — `multipart/form-data` with one field `file`. Requires authentication. Returns `202` with:
  ```json
  { "document_id": "…", "job_id": "…", "status": "PENDING", "filename": "receipt.pdf", "mime_type": "application/pdf", "size_bytes": 12345, "created_at": "…" }
  ```
- **API-DOC-02** (active) The API reads at most `max_upload_bytes + 1` bytes and rejects with `413 DOCUMENT_TOO_LARGE` if exceeded (`ENG-VAL-02`).
- **API-DOC-03** (active) The API determines the MIME type by **content sniffing** (magic bytes), not by the client-declared type or extension. Accepted: `application/pdf`, `image/png`, `image/jpeg`. Otherwise `415 UNSUPPORTED_MEDIA_TYPE`.
- **API-DOC-04** (active) Empty files and corrupted files are rejected with `422 INVALID_DOCUMENT` **at upload time** using the same validator as the engine's `DocumentValidator` (`ENG-VAL-*`). The API imports only the validation step, never the OCR step.
- **API-DOC-05** (active) Filenames are sanitized: keep `[A-Za-z0-9._-]`, replace others with `_`, max 100 characters, fallback `document`. The original filename is stored as metadata for display only; it is never used in S3 keys except through the sanitized form.
- **API-DOC-06** (active) On success the API, in this order: writes the object to S3 `uploads` (`INF-S3-02`); writes the `documents` item (`DAT-DDB-*`); writes the `jobs` item with status `PENDING` (`DAT-DDB-*`, `WRK-CLM-*`). If a later step fails, the earlier ones are compensated (S3 object deleted) and the API returns `500 INTERNAL_ERROR`.
- **API-DOC-07** (active) `GET /api/v1/documents?limit=20&cursor=<opaque>` — lists the caller's documents, newest first. `limit` 1 to 100, default 20. Admins see all documents and MAY pass `user_id` to filter. Response: `{ "items": [...], "next_cursor": "…" | null }`.
- **API-DOC-08** (active) `GET /api/v1/documents/{document_id}` — returns document metadata and processing state:
  ```json
  {
    "document_id": "…",
    "filename": "receipt.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 12345,
    "created_at": "…",
    "processing": {
      "status": "COMPLETED",
      "attempts": 1,
      "last_error_code": null,
      "updated_at": "…"
    },
    "result": { }
  }
  ```
  `processing.status` is one of `PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED` (`WRK-STM-*`). `result` is present only when status is terminal; otherwise `null`. `result` is the engine result contract (`ENG-OUT-*`) without `raw_text`.
- **API-DOC-09** (active) Access rule: owner or admin → `200`; anyone else → `404 NOT_FOUND`.
- **API-DOC-10** (active) `GET /api/v1/documents/{document_id}` MUST NOT return the S3 key or bucket name.

## 4. Administration

- **API-ADM-01** (active) `GET /api/v1/admin/users?limit&cursor` — admin only. Lists users. Others → `403 FORBIDDEN`.
- **API-ADM-02** (active) `PATCH /api/v1/admin/users/{user_id}/role` — body `{ "role": "user" | "admin" }`. Admin only. An admin MUST NOT change their own role (returns `409 CONFLICT` with a message stating that self-demotion is not allowed). This prevents the platform from ending up with no administrator.
- **API-ADM-03** (active) An existing registered account is promoted by the migration command from environment `DOCUPROCESS_BOOTSTRAP_ADMIN_EMAIL` (optional). If unset, no admin exists until an operator promotes a user with SQL (documented in the runbook).

## 5. Health and operations

- **API-OPS-01** (active) `GET /api/v1/health` — no authentication. Returns `200 {"status":"ok"}` when the process can reach RDS (`SELECT 1`) and DynamoDB (`DescribeTable` is not used; a cheap `GetItem` on a non-existent key is acceptable), `503 {"status":"degraded"}` otherwise. The ALB uses it as a target-group health check (`INF-ALB-03`).
- **API-OPS-02** (active) The health endpoint MUST NOT expose versions, hostnames, or config.

## 6. CORS and transport

- **API-CORS-01** (active) In production the browser is same-origin with the API through CloudFront, so CORS is not needed. The API still allows exactly one origin, `DOCUPROCESS_CORS_ORIGIN` (the CloudFront domain), for local development and direct testing. Methods: `GET, POST, PATCH, OPTIONS`. Headers: `Authorization, Content-Type`.
- **API-CORS-02** (active) The API does not set cookies. Authentication is the bearer token only, so CSRF protection is not needed.

## 7. Configuration (environment variables)

| Variable | Required | Notes |
|---|---|---|
| `DOCUPROCESS_DB_HOST` | yes | RDS endpoint |
| `DOCUPROCESS_DB_NAME` | yes | |
| `DOCUPROCESS_DB_USER` | yes | |
| `DOCUPROCESS_DB_PASSWORD` | yes | Loaded from `/etc/docuprocess/app.env` (`INF-UD-05`) |
| `DOCUPROCESS_AWS_REGION` | yes | `us-east-1` |
| `DOCUPROCESS_UPLOADS_BUCKET` | yes | |
| `DOCUPROCESS_DOCUMENTS_TABLE` | yes | |
| `DOCUPROCESS_JOBS_TABLE` | yes | |
| `DOCUPROCESS_CORS_ORIGIN` | yes | |
| `DOCUPROCESS_MAX_UPLOAD_BYTES` | no | Default `5242880` |
| `DOCUPROCESS_BOOTSTRAP_ADMIN_EMAIL` | no | Used by migration only |

Configuration is loaded once at startup into a typed settings object. Missing required variables cause startup failure with a clear message naming the variable (never its value).

## 8. Run command

`uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2` (wrapped by systemd, `INF-UD-07`).

## 9. Acceptance

- **API-ACC-01** (active) Every endpoint above has at least one contract test covering success and the main error code (`TST-UNIT-API-*`).
- **API-ACC-02** (active) OpenAPI is generated by FastAPI and committed as `docs/openapi.json` by `make package`.

DOCUPROCESS_DB_SSL_CA is required in production and points to the AWS RDS CA bundle installed at boot (ADR-037).

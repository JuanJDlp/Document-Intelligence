# ADR-009: Uploads go through the API as multipart, with no presigned URLs

- **Status:** Accepted
- **Area:** API

## Context
The API must reject unsupported or oversize files before storage. Presigned URLs would let the browser write to S3 directly, skipping that check.

## Decision
`POST /api/v1/documents` accepts multipart. The API validates type and size, then writes to S3.

## Consequences
- Files pass through the ALB and the instance (max 5 MiB).
- No extra IAM use for presigned URL generation.

Specs: `04-api.md`

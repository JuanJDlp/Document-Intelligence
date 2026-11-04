# ADR-013: Upload limit 5 MiB, one PDF page, images up to 10000 px

- **Status:** Accepted
- **Area:** Engine / API

## Context
The synchronous OCR path has practical size limits. Limits must be testable.

## Decision
Max 5 MiB (`5242880` bytes), max 1 PDF page, max image side 10000 px. The API and the engine use the same size limit.

## Consequences
- Larger or multi-page receipts are rejected with a clear error.

Specs: `06`, `04`, `03` (`max_upload_bytes`)

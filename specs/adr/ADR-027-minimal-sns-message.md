# ADR-027: SNS messages contain only IDs, status, and time

- **Status:** Accepted
- **Area:** Notifications

## Context
Notifications go to email subscribers. Extracted data is personal.

## Decision
Message: `event`, `document_id`, `job_id`, `status`, `occurred_at`. No filename, amounts, NIT, or user email.

## Consequences
- Users open the portal to see the result.

Specs: `05-worker.md`

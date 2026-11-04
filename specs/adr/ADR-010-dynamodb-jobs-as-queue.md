# ADR-010: The DynamoDB `jobs` table is the job queue; no SQS

- **Status:** Accepted
- **Area:** Data / Worker

## Context
SQS is not in the sandbox service list (`02` section 0), and `CON-SVC-01` forbids unlisted services. The course names DynamoDB for state and results.

## Decision
Jobs are items in the `jobs` table. The worker claims them with a conditional write on a status GSI (`gsi_status_available`) and a lease (`available_at`).

## Consequences
- State and queue are one record: no dual-write inconsistency.
- More code owned by us: leases, backoff, retries. Polling every 5 s, not long polling.
- Replacing it with SQS requires updating this ADR and verifying SQS is allowed.

Specs: `05-worker.md`, `07-data-model.md`

Evidence (2026-11-03, no former question): `sqs:ListQueues` returned AccessDenied for the lab role in the sandbox.

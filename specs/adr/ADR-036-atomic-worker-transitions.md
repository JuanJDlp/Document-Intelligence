# ADR-036: Atomic job and document transitions

- **Status:** Accepted
- **Area:** Worker / Data integrity

## Decision

Use DynamoDB TransactWriteItems for claiming, retrying, expiring and completing jobs. The job update checks its observed status, attempt count and available_at; transitions from RUNNING also check lease_owner. Completion and retry require an unexpired lease. The document mirror changes in the same transaction. A stale worker cannot change either item.

The document and job tables already grant UpdateItem, which authorizes transactional updates too. Admin document listing additionally needs Scan on the document table. Real instance-role access remains a sandbox acceptance check.

SNS is published only by the winner of a terminal transition. Publication is retried three times and recorded as SENT or FAILED. A crash between commit and publish can lose the notification, and an ambiguous network response can cause duplicate delivery. Version 1 does not promise exactly-once email delivery; automatic recovery of notifications is deferred and documented.

## Verification

Offline tests cover competing claims, expired leases, stale completion, retries, terminal immutability and SNS failures. Cloud authorization and email delivery require live acceptance tests.

Requirements: WRK-STM-03, WRK-PER-01..03, WRK-NOT-01..04, DAT-ACC-02.

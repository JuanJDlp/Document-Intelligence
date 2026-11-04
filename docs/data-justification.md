# Data design justification: RDS (MySQL) and DynamoDB

The system uses two data stores. This document explains why each one holds the data it holds, and what we give up by splitting them. The detailed schemas are in `specs/07-data-model.md`.

## 1. Summary

| Data | Store | Why |
|---|---|---|
| Users, passwords (hashed), sessions, roles | RDS MySQL 8.0 | Relational rules: unique emails, a foreign key from sessions to users, transactions, role checks |
| Document metadata | DynamoDB `documents` | Key-based access by `document_id`; flexible, nested result; listing by user through an index |
| Processing jobs and queue | DynamoDB `jobs` | Conditional writes for safe claiming; a status index for the worker; no separate queue |
| Extraction results | DynamoDB `documents` (attribute `result`) | Result shape is nested and may change between engine versions; read together with the document |

## 2. Why RDS for users, sessions, and roles

- **Constraints in the schema.** `users.email` must be unique, and `sessions.user_id` must reference an existing user. MySQL enforces both. In DynamoDB, uniqueness of email would need a second item and a transaction across two writes.
- **Stable, small schema.** Three tables with fixed columns. This is the kind of data SQL models well.
- **Transactions.** Creating a user and assigning a role, or revoking a session, are single-row updates with clear rules. They do not need the scale-out that motivates DynamoDB.
- **Admin queries.** Listing users in order (`API-ADM-01`) and filtering by role are simple SQL queries with indexes.

Costs we accept:
- RDS is Single-AZ, which the sandbox requires (`ADR-003`). A database failure stops logins and uploads until it is restored.
- Scaling writes beyond one instance is not designed for. This is not a requirement at course scale.

## 3. Why DynamoDB for documents, jobs, and results

- **Access pattern is key-based.** Almost every request reads one item by `document_id` or `job_id`. DynamoDB serves these with single-digit millisecond reads and no connection pool.
- **Worker claiming.** A job is claimed with one conditional update: `status = PENDING AND available_at <= now`. The condition makes two workers on two instances unable to claim the same job (`WRK-CLM-02`). A status index (`gsi_status_available`) lets the worker find due jobs.
- **Single record for state and queue.** The queue is the `jobs` table (`ADR-010`). The job state and the queue entry are the same item, so they cannot disagree. With SQS, a message and a database row would have to be written together.
- **Flexible results.** The extraction result has optional fields, lists of line items, warnings, and confidence maps. Storing it as one nested attribute avoids a schema change every time the engine adds a field.
- **No capacity planning.** On-demand billing (`PAY_PER_REQUEST`) suits bursty uploads.

Costs we accept:
- No joins. The API reads `documents` for the detail page. It does not need data from RDS to answer status queries, but it does need RDS to check the caller's identity and role, and it does that before reading DynamoDB.
- The admin "all documents" listing uses `Scan`, which is acceptable only at sandbox volume (`DAT-ACC-04`).
- Items are limited to 400 KB. Results are capped at 100 KB, and line items are truncated with a warning if needed (`WRK-PER-04`).
- Writes to `documents` and `jobs` are two operations, not one transaction. The worker writes the result first and then the terminal job state, and a lost lease discards the result (`WRK-PER-01/02`).

## 4. Why not SQS for the job queue

- SQS is not in the sandbox service list (`specs/02-aws-sandbox-constraints.md` section 0). Constraint `CON-SVC-01` forbids services outside that list.
- The course brief names DynamoDB for processing metadata and history, and SNS for notifications.
- With the `jobs` table, the queue and the job state are one record, so there is no dual write between a queue and a database.
- What we give up: SQS provides visibility timeouts, dead-letter queues, and long polling. We implement leases, backoff, and retry limits ourselves (`ADR-026`, `WRK-PRC-07`), and the worker polls every 5 seconds instead of reacting immediately.

If SQS is later confirmed as allowed, `ADR-010` is edited to the new design, and the worker and data-model specs change with it.

## 5. Why not one store for everything

- Putting users in DynamoDB would lose the uniqueness and foreign-key guarantees above.
- Putting documents in RDS would make every upload a relational write with a result blob, and it would not use the key-based access pattern.
- Two stores with clear ownership keep each rule in the store that enforces it best. The API is the only component that reads both.

## 6. Data retention and privacy

- Passwords are stored only as Argon2id hashes. Session tokens are stored only as SHA-256 hashes (`ADR-019`, `ADR-021`).
- Raw OCR text is never stored (`ADR-018`).
- Notifications contain only IDs and status (`ADR-027`).
- RDS is not encrypted at rest because KMS is list-only in the sandbox (`ADR-032`).

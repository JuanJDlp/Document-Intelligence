# ADR-026: Lease-based job claiming with conditional writes

- **Status:** Accepted
- **Area:** Worker

## Context
Several instances run workers at once. A crashed worker must not block a job forever.

## Decision
Claim = conditional update that sets `RUNNING`, `lease_owner`, and `available_at = now + 300 s`. Expired leases are reclaimable up to `max_attempts`.

## Consequences
- Safe with many workers. A lost lease discards the result (`WRK-PER-02`).

Specs: `05-worker.md`, `07-data-model.md`

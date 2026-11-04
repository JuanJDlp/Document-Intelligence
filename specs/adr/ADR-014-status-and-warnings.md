# ADR-014: Engine status is completed, partial, or failed; warnings never invalidate

- **Status:** Accepted
- **Area:** Engine

## Context
The draft mixed status values and error codes. The course asks for predictable handling of partial data.

## Decision
`status` ∈ {`completed`, `partial`, `failed`}. `partial` has no error. Warnings never set `validation.is_valid = false`.

## Consequences
- The worker maps status directly to job status (`05` section 4).

Specs: `06-receipt-extraction-engine.md`

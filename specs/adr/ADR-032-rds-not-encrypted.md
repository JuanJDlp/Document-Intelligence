# ADR-032: RDS storage encryption is not enabled

- **Status:** Accepted
- **Area:** Security

## Context
Default RDS encryption uses a KMS key. The sandbox has KMS list access only (`CON-KMS-01`).

## Decision
`storage_encrypted = false`. EBS root volumes are encrypted; S3 uses SSE-S3.

## Consequences
- Data at rest in RDS is not encrypted. Documented in `docs/risks-and-exceptions.md`.

Specs: `09-security-observability.md`

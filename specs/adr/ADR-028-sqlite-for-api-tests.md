# ADR-028: API unit tests use SQLite; production uses MySQL

- **Status:** Accepted
- **Area:** Testing

## Context
Tests must run offline and fast. Production MySQL is only in the sandbox.

## Decision
API contract tests run on SQLite with equivalent column types. The migration test checks constraints on MySQL in the sandbox when available.

## Consequences
- Some MySQL-specific behavior is verified only in the sandbox.

Specs: `07-data-model.md`, `10-testing-and-acceptance.md`

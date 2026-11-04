# ADR-021: Argon2id for password hashing

- **Status:** Accepted
- **Area:** Security

## Context
Passwords must be stored with a memory-hard algorithm.

## Decision
Argon2id via `argon2-cffi`, default or stronger parameters.

## Consequences
- Login always runs one hash verification to avoid timing leaks (`API-AUTH-04`).

Specs: `04-api.md`, `09-security-observability.md`

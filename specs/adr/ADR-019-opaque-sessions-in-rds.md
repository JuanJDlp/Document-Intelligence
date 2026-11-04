# ADR-019: Opaque session tokens stored hashed in RDS, not JWT

- **Status:** Accepted
- **Area:** Auth

## Context
The course asks for session management. JWT cannot be revoked on logout without a server-side list.

## Decision
Random 32-byte tokens. Store only `SHA-256(token)` in `sessions`. Lifetime 8 hours. Logout sets `revoked_at`.

## Consequences
- One DB lookup per authenticated request.

Specs: `04-api.md`, `07-data-model.md`

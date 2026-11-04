# ADR-020: Two roles, `user` and `admin`

- **Status:** Accepted
- **Area:** Auth

## Context
The course asks for permission assignment. Finer roles are not needed for the demo.

## Decision
`user` sees own documents; `admin` sees all and can change roles. Self-demotion is blocked.

## Consequences
- The first admin comes from a bootstrap setting or SQL.

Specs: `04-api.md`

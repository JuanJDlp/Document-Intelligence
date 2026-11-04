# ADR-003: Relational store is RDS MySQL 8.0, Single-AZ

- **Status:** Accepted
- **Area:** Data

## Context
The course diagram shows MySQL. The sandbox allows Aurora, MySQL, PostgreSQL, and MariaDB, only Single-AZ, `db.t2`/`db.t3` up to `medium`.

## Decision
RDS MySQL 8.0 on `db.t3.micro`, `multi_az = false`, 20 GB `gp2`, not publicly accessible, in private DB subnets.

## Consequences
- RDS is a single point of failure. Accepted risk (`docs/risks-and-exceptions.md`).
- The database holds only users, sessions, and roles (ADR-010 covers documents and jobs).

Specs: `07-data-model.md`, `03-infrastructure.md`

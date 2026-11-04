# ADR-004: Two-AZ subnet layout (deviation from the course diagram)

- **Status:** Accepted
- **Area:** Network

## Context
The course diagram shows one private subnet (`10.0.1.0/24`). An ALB and an Auto Scaling Group spanning two AZs require two public and two private subnets. A DB subnet group also requires two AZs even for Single-AZ RDS.

## Decision
VPC `10.0.0.0/16`. Public: `10.0.101.0/24`, `10.0.102.0/24`. App (private): `10.0.1.0/24`, `10.0.2.0/24`. DB (private): `10.0.11.0/24`, `10.0.12.0/24`. The first private subnet keeps the diagram CIDR.

## Consequences
- The architecture diagram in `docs/` shows this real layout, not the illustration.

Specs: `01-architecture.md`, `03-infrastructure.md`

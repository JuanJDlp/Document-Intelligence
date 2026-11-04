# ADR-023: Lambda is not used

- **Status:** Accepted
- **Area:** Compute

## Context
Verified 2026-11-03 (was Q-007): the instance role trusts only `ec2.amazonaws.com`, and creating roles is denied (`CON-IAM-01`). Lambda cannot run under the course roles.

## Decision
All compute runs on EC2 in the Auto Scaling Group. No Lambda resources.

## Consequences
- The API and the worker run on the same instances.

Specs: `01-architecture.md`, `02-aws-sandbox-constraints.md`

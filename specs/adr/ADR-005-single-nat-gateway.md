# ADR-005: One NAT gateway, not highly available

- **Status:** Accepted
- **Area:** Network

## Context
Private instances need outbound access for package installs and AWS APIs. One NAT gateway per AZ doubles the cost, and the sandbox budget is limited.

## Decision
One NAT gateway with one Elastic IP in `public-a`.

## Consequences
- If AZ `a` fails, private instances lose outbound access. Accepted risk, documented.
- Gateway endpoints for S3 and DynamoDB reduce NAT traffic (free).

Specs: `03-infrastructure.md` (`INF-NET-04`). NAT creation verified as allowed (`specs/answered-questions.md`, Q-004).

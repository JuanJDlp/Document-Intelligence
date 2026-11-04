# ADR-006: Reach SNS through the NAT gateway, without an interface endpoint

- **Status:** Accepted
- **Area:** Network

## Context
An SNS interface endpoint costs per hour and per AZ. The NAT gateway already exists for other outbound traffic.

## Decision
Instances publish to SNS through the NAT gateway. No SNS interface endpoint.

## Consequences
- Cheaper; SNS traffic leaves the VPC through NAT.

Specs: `01-architecture.md`

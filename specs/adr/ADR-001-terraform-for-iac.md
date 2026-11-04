# ADR-001: Use Terraform for infrastructure as code

- **Status:** Accepted
- **Area:** Infrastructure

## Context
The course allows Terraform and CloudFormation. The sandbox gives no IAM write access, so the tool must not need extra roles.

## Decision
Use Terraform (`>= 1.6`, AWS provider `~> 5.0`) in a single root module composed of child modules. Do not use CloudFormation.

## Consequences
- Modular, readable plans; local state, git-ignored (`INF-STATE-01`).
- Terraform must never read or write IAM (`CON-IAM-02`).

Specs: `03-infrastructure.md`

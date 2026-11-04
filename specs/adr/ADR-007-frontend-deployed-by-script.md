# ADR-007: Frontend files are uploaded by a script, not by Terraform

- **Status:** Accepted
- **Area:** Delivery

## Context
Terraform manages resources, not file contents. Frontend changes are frequent.

## Decision
`scripts/deploy_frontend.sh` syncs `app/frontend/` to the frontend bucket and creates a CloudFront invalidation.

## Consequences
- Terraform stays free of file uploads. Frontend iteration is fast.

Specs: `03-infrastructure.md`, `08-frontend.md`

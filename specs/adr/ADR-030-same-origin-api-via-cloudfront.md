# ADR-030: CloudFront routes `/api/*` to the ALB, so frontend and API are same-origin

- **Status:** Accepted
- **Area:** Network / Frontend

## Context
The frontend is served over HTTPS by CloudFront. The ALB has no certificate. Browsers block HTTP API calls from an HTTPS page (mixed content).

## Decision
CloudFront has an S3 origin (default) and an ALB origin for `/api/*` (HTTP to the ALB). The frontend uses the relative path `/api/v1`.

## Consequences
- No CORS needed in production; no host name in frontend code.
- CloudFront creation is verified as allowed (`specs/answered-questions.md`, Q-005).

Specs: `01-architecture.md`, `03-infrastructure.md`, `08-frontend.md`

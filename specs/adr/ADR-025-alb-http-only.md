# ADR-025: The ALB listens on HTTP only

- **Status:** Accepted
- **Area:** Network / Security

## Context
No custom domain or ACM certificate is available (`CON-DNS-02`).

## Decision
ALB listener on port 80. Browsers reach it only through CloudFront (ADR-030).

## Consequences
- Accepted risk: traffic between CloudFront and the ALB is not encrypted. Documented in `docs/risks-and-exceptions.md`.

Specs: `03-infrastructure.md`, `09-security-observability.md`

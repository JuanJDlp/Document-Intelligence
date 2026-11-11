# Risks and verification boundaries

- The current local flow uses SQLite for identity and moto for AWS adapters. MySQL-specific DDL, TLS, instance-role resource-policy authorization and real email delivery need sandbox verification.
- EC2 API/worker processes run on the same ASG. The application tier has two instances, but RDS is Single-AZ and there is one NAT gateway, as required/accepted by the sandbox design.
- CloudFront terminates HTTPS; its ALB origin uses HTTP. The ALB security group accepts public HTTP, a documented sandbox limitation.
- RDS storage encryption is disabled under the existing sandbox KMS decision. This deployment is for synthetic documents only.
- SNS publication is outside the DynamoDB transaction. A crash after commit can lose a notification; an uncertain publish response or SNS delivery can duplicate email. Failed publish attempts are recorded; automatic recovery is out of scope.
- Admin document listing scans and sorts the sandbox dataset. It is not intended for large production datasets.
- A result larger than 100 KB after truncating line items is rejected with WORKER_RESULT_TOO_LARGE; it is not persisted.
- uv.lock fixes development/runtime versions. Package releases export the same runtime versions; updates require deliberate validation.
- Frontend frame-ancestors protection is delivered as a CloudFront response header, since browsers ignore that directive in a CSP meta tag.
- AWS state and credentials are operator-local. Do not infer an empty AWS account from absent local state. Before applying, reconcile existing resources and state.

Historical sandbox probes are recorded in specs/answered-questions.md and ADR-033..035. They are evidence for those past sessions, not confirmation of current resources. The latest session check returned SESSION INVALID OR EXPIRED; identity, region, existing resources/state and instance-profile access must be rechecked after renewal. Q-006 (instance quota) remains open. Automatic dependency updates are intentionally disabled; lock changes require manual review and the validation suite (SEC-DEP-*).

The Tesseract adapter returns text lines, not structured line-item records. Its results therefore have an empty line_items list; structured-provider fixtures verify the engine mapping separately. merchant_address and customer_id remain null by ADR-029. Extraction is heuristic and may return partial/failed results for unfamiliar layouts; confidence comes from OCR rather than a guarantee of correctness.
- Login floods exhaust instance memory. Each Argon2id verification allocates 64 MiB and a `t3.micro` has 1 GiB. Observed 2026-11-10: 24 concurrent login clients made the API process die and the ALB return `502` for almost every request, and the ASG replaced instances as unhealthy instead of scaling out. With 4 clients, logins succeeded and instance CPU reached about 89 %. There is no login rate limiting in version 1; the load test (`make load`) keeps concurrency low on purpose.
- Detailed EC2 monitoring is denied in the lab (`ec2:MonitorInstances`). Auto Scaling reacts to 5-minute CPU datapoints, so scale-out takes about 8–12 minutes of sustained load instead of 2–3.

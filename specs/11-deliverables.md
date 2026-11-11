# 11 — Deliverables

These are the course deliverables (brief, section 5). They are written for humans and live in `docs/`. An agent produces them from the specs and the actual deployed state; it must not describe resources that were not verified.

## 1. Repository (`DLV-REPO-*`)

- **DLV-REPO-01** (active) Git repository with the structure in `AGENTS.md` section 7.
- **DLV-REPO-02** (active) `README.md` explains: what the project is, prerequisites (AWS Academy CLI credentials, Terraform, Python 3.12, uv), the commands in `Makefile`, and a link to `docs/deployment-guide.md`.
- **DLV-REPO-03** (active) Terraform modularized under `infra/terraform/modules/` (`INF-TOOL-02`) with `.terraform.lock.hcl` committed.
- **DLV-REPO-04** (active) userData script in `infra/terraform/templates/userdata.sh.tftpl` (`INF-UD-*`).
- **DLV-REPO-05** (active) `.gitignore` excludes: `.venv/`, `__pycache__/`, `dist/`, `*.tfstate*`, `.terraform/`, `terraform.tfvars`, `.env`, `config.js` with real values if ever created.

## 2. Architecture documentation (`DLV-ARC-*`)

- **DLV-ARC-01** (active) `docs/architecture.md` contains the reference architecture diagram that matches the deployed topology: two AZs, public and private subnets, the NAT gateway, endpoints, ALB, ASG, CloudFront with the `/api/*` origin, S3, DynamoDB, RDS, SNS, CloudWatch, and CloudTrail. The diagram is source-controlled as Mermaid in the document (and MAY be exported to PNG). It MUST NOT copy the course illustration (see `01` section 4).
- **DLV-ARC-02** (active) The diagram shows the request flows from `01` section 5 and labels each arrow with the protocol and port.
- **DLV-ARC-03** (active) `docs/architecture.md` lists the sandbox constraints that shaped the design, referencing `02` section 0 and the table of deviations.
- **DLV-ARC-04** (active) `docs/architecture.html` is a self-contained visual companion to `docs/architecture.md` for the presentation: topology with AWS Architecture Icons, the upload and processing sequence, the job state machine, instance bootstrap, security groups, and data placement. It loads nothing from the network (icons are inlined as SVG symbols), and it MUST NOT contradict `docs/architecture.md` or `infra/terraform/`. When the topology changes, both files are updated in the same change. Verification: open the file offline in a browser and compare each node and port with `terraform output` and `01` section 5.

## 3. Data justification (`DLV-DATA-*`)

- **DLV-DATA-01** (active) `docs/data-justification.md` explains RDS vs DynamoDB for this project, with at least these points, each tied to a concrete use in `07-data-model.md`:
  - **RDS (MySQL)** holds users, sessions, and roles: relational integrity (unique email, foreign key sessions → users), transactional updates, and a small, stable schema.
  - **DynamoDB** holds documents, jobs, and results: key-based access by `document_id` and `job_id`, a status-based index for the worker's claim query, flexible result shape, and on-demand scaling without a single writer bottleneck.
  - Trade-offs: RDS is Single-AZ (sandbox restriction, accepted risk); DynamoDB has no joins, so the API composes data from both stores where needed (the API reads `documents` only).
- **DLV-DATA-02** (active) It also documents why the job queue is a DynamoDB table and not SQS (`ADR-010`).

## 4. Deployment guide (`DLV-DEP-*`)

- **DLV-DEP-01** (active) `docs/deployment-guide.md` is a step-by-step guide to deploy from an empty sandbox. It follows `03` section 15 and the Makefile targets in `10` section 3.
- **DLV-DEP-02** (active) Prerequisites section lists: sandbox started, CLI credentials exported, region `us-east-1`, the instance profile name discovered by the `aws-sandbox` skill, and the `alert_email` address ready for confirmation.
- **DLV-DEP-03** (active) Troubleshooting section covers at least these known problems, each with symptom, cause, and fix:
  - ALB targets unhealthy: check `journalctl -u docuprocess-api` and the bootstrap log `/var/log/docuprocess-bootstrap.log`.
  - userData cannot download the release: check the artifacts bucket and the release version variable.
  - Instances cannot reach package repositories or the Python toolchain: check the NAT gateway and route tables.
  - RDS unreachable from app: check `db-sg` ingress from `app-sg`.
  - Terraform `AccessDenied` on a service: check `02` section 0 and the constraint guard.
  - SNS email not received: confirm the subscription.
  - CloudFront returns stale content: invalidate `/*`.
  - Tesseract missing on the instance: check the bootstrap log; the dnf package name may differ (`ADR-012`).
- **DLV-DEP-04** (active) Teardown section: `make destroy`, and the manual check that the CloudTrail bucket and the artifacts bucket are emptied if Terraform cannot delete them (the buckets are emptied first by `scripts/empty_buckets.sh`, see `ADR-035`).

## 5. Risks and exceptions (`DLV-RISK-*`)

- **DLV-RISK-01** (active) `docs/risks-and-exceptions.md` lists every row of `09` section 3 with its justification and the accepted state.
- **DLV-RISK-02** (active) Lists which sandbox facts were verified and which were not (`Q-*` resolutions).

## 6. Live demonstration (`DLV-DEMO-*`)

- **DLV-DEMO-01** (active) `docs/demo-script.md` is the script for the live demo: deploy from clean template, upload a document through the browser, watch the job, receive the SNS email, show the DynamoDB item, generate load to show Auto Scaling, show the CloudWatch alarm and the CloudTrail event.
- **DLV-DEMO-02** (active) The demo script lists the exact commands and the expected output of each step.

## 7. Acceptance

- **DLV-ACC-01** (active) All files named in sections 1–6 exist and are reviewed against the `TST-E2E-*` checklist results.
- **DLV-ACC-02** (active) Documents reference requirement IDs where they state a decision or a constraint.

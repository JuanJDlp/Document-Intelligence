# 10 — Testing, verification and acceptance

## 1. Principles

- **TST-PRN-01** (active) Every test that claims a requirement ID names it in its name or docstring (`test_eng_val_02_...`). `make test` output MUST allow tracing from a requirement to a test.
- **TST-PRN-02** (active) `make test` runs without network access, without AWS credentials, and without a real OCR call. AWS interactions use `moto` or fakes.
- **TST-PRN-03** (active) Tests never use real receipts. Samples are synthetic (`ENG-TST-01`, `SEC-DATA-*`).
- **TST-PRN-04** (active) Anything that requires the sandbox is verified manually, is listed in the acceptance checklist (section 6), and is reported as **unverified** until executed.

## 2. Test layers

| Layer | Location | Tooling | Scope |
|---|---|---|---|
| Engine unit | `app/receipt_engine/tests/` | pytest | `ENG-*` |
| Engine golden | `app/receipt_engine/tests/golden/` | pytest, `samples/receipts/` | `ENG-TST-03` |
| API contract | `app/api/tests/` | pytest, FastAPI `TestClient`, SQLite | `API-*` |
| Worker unit | `app/worker/tests/` | pytest, `moto` | `WRK-*`, `DAT-ACC-07` |
| Cross-component | `tests/integration/` | pytest, `moto`, fake OCR | upload → worker → result, without real AWS |
| Infrastructure static | `scripts/check_constraints.sh`, `terraform validate` | bash, terraform | `CON-*`, `INF-*` |
| Security | `tests/security/` | pytest | `SEC-LOG-03`, `TST-SEC-01` |
| Live sandbox | `scripts/smoke_test.py`, manual checklist | Python `httpx` | `TST-E2E-*` |

## 3. Makefile targets (normative)

The `Makefile` at the root is the only entry point for humans and agents. Each target is idempotent.

| Target | Command semantics | Requirement |
|---|---|---|
| `setup` | Creates `.venv` per Python package with `uv` and installs dev extras | `TST-MK-01` |
| `lint` | `ruff check` and `ruff format --check` on `app/ tests/ scripts/`; `terraform fmt -check -recursive infra/terraform`; `scripts/check_constraints.sh`; `scripts/check_frontend.sh` | `TST-MK-02` |
| `typecheck` | `mypy --strict app/receipt_engine/src`; `mypy app/worker/src app/api/src` | `TST-MK-03` |
| `test` | `pytest app/receipt_engine app/api app/worker tests` | `TST-MK-04` |
| `tf-validate` | `terraform -chdir=infra/terraform init -backend=false && terraform -chdir=infra/terraform validate` | `TST-MK-05` |
| `tf-plan` | `terraform -chdir=infra/terraform plan -var-file=terraform.tfvars` (read-only) | `TST-MK-06` |
| `bootstrap-artifacts` | `terraform apply -target=module.storage` (requires explicit user approval) | `TST-MK-07` |
| `package` | Builds `dist/docuprocess-<version>.tar.gz` and `docs/openapi.json` | `TST-MK-08` |
| `publish` | Runs `scripts/publish_release.sh` to upload the tarball to the artifacts bucket (requires approval) | `TST-MK-09` |
| `deploy` | `terraform apply` with `release_version` (requires explicit approval) | `TST-MK-10` |
| `deploy-frontend` | Runs `scripts/deploy_frontend.sh` (requires approval) | `TST-MK-11` |
| `smoke` | Runs `scripts/smoke_test.py` against `SMOKE_BASE_URL` | `TST-MK-12` |
| `destroy` | `terraform destroy` (requires explicit approval, prints the plan first) | `TST-MK-13` |

- **TST-MK-14** (active) Targets that create or delete billable AWS resources (`bootstrap-artifacts`, `publish`, `deploy`, `deploy-frontend`, `destroy`) MUST NOT run without explicit approval from the user in the current conversation (`AGENTS.md` section 8).

## 4. Static guards

- **TST-CON-01** (active) `scripts/check_constraints.sh` fails when any of these appear under `infra/terraform/`:
  - `aws_iam_role`, `aws_iam_policy`, `aws_iam_role_policy`, `aws_iam_role_policy_attachment`, `aws_iam_instance_profile`, `data "aws_iam_role"`;
  - `aws_lambda_`, `aws_api_gateway`, `aws_ecs_`, `aws_eks_`, `aws_route53_`, `aws_acm_certificate`, `aws_kms_key`;
  - `aws_key_pair`, port `22` in any security group rule;
  - `multi_az\s*=\s*true`, `publicly_accessible\s*=\s*true`, `key_name`;
  - `instance_type` values outside `t2.*`/`t3.*` from `nano` to `medium`;
  - `aws_ebs_volume` or `volume_size` above 35 GB for EC2 and `allocated_storage` above 100 GB for RDS.
- **TST-CON-02** (active) `scripts/check_constraints.sh` also fails when `app/receipt_engine/src` imports `boto3`, `botocore`, `fastapi`, `sqlalchemy`, `pymysql`, or `worker`/`api` packages (`ENG-SCOPE-02`). Implemented as a test in `app/receipt_engine/tests/test_boundaries.py` so it also runs under `make test`.
- **TST-CON-03** (active) `terraform plan` output is reviewed by the operator for the forbidden types listed in `02` section 3 before any apply (`CON-*`).
- **TST-LINT-02** (active) `scripts/check_frontend.sh` fails on `innerHTML` in `app/frontend/assets/` and on external `<script src>` or `<link href>` hosts (`FE-ACC-02`).

## 5. Test data

- **TST-DATA-01** (active) `samples/receipts/` holds synthetic documents: at least one PDF receipt, one PNG receipt, one JPEG receipt, one invoice with line items, one receipt with a comma-decimal amount, one receipt with a missing total, one receipt with a negative total (validation failure), one blank image (no text), one multi-page PDF, one encrypted PDF, one text file renamed `.pdf`.
- **TST-DATA-02** (active) Each sample has `<name>.ocr.json` (recorded provider output) and `<name>.expected.json` (hand-written expected engine output). `scripts/make_samples.py` MAY generate the PDF/PNG files but MUST NOT generate expected outputs.
- **TST-DATA-03** (active) Synthetic merchants and NIT numbers only. NITs are generated with the DIAN check digit algorithm (`ENG-NRM-04`) and documented in `samples/README.md`.

## 6. Acceptance checklist (sandbox)

Run in order after `make deploy`. Each item is verified and recorded with date and output.

| ID | Check | Requirement |
|---|---|---|
| TST-E2E-01 | `make tf-validate` passes on a clean clone | `INF-ACC-01` |
| TST-E2E-02 | `make tf-plan` shows no forbidden resource type | `INF-ACC-02`, `TST-CON-03` |
| TST-E2E-03 | Full deploy from empty sandbox succeeds, no manual console steps except SNS email confirmation | `INF-ACC-03` |
| TST-E2E-04 | ALB target group: 2 healthy instances on `/api/v1/health` | `INF-ALB-03` |
| TST-E2E-05 | CloudFront serves `/` and `/api/v1/health` over HTTPS | `INF-CDN-05`, `ADR-030` |
| TST-E2E-06 | Register, login, upload a sample PDF receipt via the browser | `PRD-F-01..03` |
| TST-E2E-07 | Job reaches a terminal state within 2 minutes; the `documents` item contains `result` | `WRK-ACC-02` |
| TST-E2E-08 | Exactly one SNS message for that job; the message contains no extracted data | `WRK-NOT-02` |
| TST-E2E-09 | Upload of a 6 MB file is rejected with `413`; upload of a text file renamed `.pdf` is rejected with `415` | `API-DOC-02/03` |
| TST-E2E-10 | `terraform apply` immediately again shows no changes | `INF-ACC-04` |
| TST-E2E-11 | Scale-out: generate CPU load on one instance; ASG desired capacity increases; never above 4 | `INF-ASG-04`, `INF-ASG-01` |
| TST-E2E-12 | Alarm `asg-cpu-high` triggers and notifies `ops-alarms` in test mode (set threshold low via variable for the test only) | `INF-MON-01`, `OBS-ALM-01` |
| TST-E2E-13 | CloudTrail trail is logging, or the blocker is documented (`answered-questions.md`, Q-003) | `INF-AUD-02/03` |
| TST-E2E-14 | Operator reaches an instance with SSM Session Manager and no port 22 is open | `CON-EC2-05`, `SEC-IAM-03` |
| TST-E2E-15 | Logs for the flow contain no sensitive values (manual grep on `journalctl` output) | `SEC-LOG-02` |

## 7. Smoke test script (`scripts/smoke_test.py`)

- **TST-SMK-01** (active) Reads `SMOKE_BASE_URL` (CloudFront domain). Performs: health, register (unique email), login, upload of the sample PDF, poll until terminal (max 120 s), fetch the document, check `result.extracted_data` keys exist, logout.
- **TST-SMK-02** (active) Exits `0` on success and non-zero on any failed step, printing the step name and the HTTP status only. No tokens or response bodies are printed.
- **TST-SMK-03** (active) Uses a random test email in the form `smoke+<uuid>@example.com`.

## 8. Definition of done (repository level)

A release is ready when:
1. `make lint`, `make typecheck`, `make test`, `make tf-validate` pass.
2. `make package` succeeds and `docs/openapi.json` is up to date.
3. Every requirement in `specs/` marked `active` has at least one test or a checklist entry in section 6.
4. `specs/open-questions.md` has no `open` item that blocks the release.
5. The deliverables in `11-deliverables.md` exist.

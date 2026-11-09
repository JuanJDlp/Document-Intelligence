# AGENTS.md — DocuProcess Cloud

This file is the entry point for any AI coding agent working in this repository.
It defines how the project is built, where the requirements live, and the rules you must follow.

Read this file completely before doing anything else.

---

## 1. What this project is

**DocuProcess Cloud** is a SaaS platform for asynchronous processing of documents (receipts and invoices, PDF and images) uploaded by enterprise users.

It is the final project for the course *Infraestructura III* (Universidad ICESI). The graded deliverables are:

1. A Git repository with Infrastructure as Code (Terraform) plus application code.
2. Technical documentation (architecture diagram, RDS vs DynamoDB justification, step-by-step deployment guide with troubleshooting).
3. A live deployment demo from a clean account.

The original course brief is `guia_proyecto_final.pdf` (in Spanish). It is the **original source of truth for scope and grading**. The specs in `specs/` are the working translation of it into implementable requirements.

The target environment is the **AWS Academy Sandbox (Vocareum)** in `us-east-1`. It has strict IAM and service restrictions. They are listed in `specs/02-aws-sandbox-constraints.md`. Violating them breaks the project.

---

## 2. Source of truth and precedence

When sources disagree, use this order:

1. `guia_proyecto_final.pdf` — the course requirements. Never contradict it silently.
2. `specs/` — the implementable requirements. Code must conform to them.
3. `specs/adr/` — decisions already taken. Do not re-litigate them; propose a new decision instead.
4. `AGENTS.md` — how to work.
5. Existing code — only a reference. Code that contradicts `specs/` is a bug unless a spec change is proposed.

**Never resolve a contradiction by silently picking one side.** Record it in `specs/open-questions.md` and tell the user.

---

## 3. Mandatory reading order

Before writing code for any task:

1. `AGENTS.md` (this file).
2. `specs/README.md` — the spec index and ID scheme.
3. The spec file(s) that cover your task (see the index).
4. `specs/open-questions.md` — some items may block your task.
5. `specs/adr/` — some choices are already fixed.

Do not start from the code. Start from the spec.

---

## 4. Spec-driven workflow (mandatory)

Every change follows this sequence. Do not skip steps.

1. **Locate the requirement.** Find the requirement IDs (for example `ENG-VAL-03`, `INF-NET-02`) that your change satisfies.
2. **Spec first.** If no requirement covers the change, add or update a spec first, using `specs/templates/feature-spec.md` as the form. Get the spec consistent before touching code.
3. **Acceptance tests first when practical.** Write tests that reference requirement IDs in their docstrings or names (for example `test_eng_val_03_total_negative_is_rejected`).
4. **Implement** the smallest change that makes the requirement true.
5. **Verify** with the commands in section 8. Report failures honestly, with the output.
6. **Trace.** In your final report, list the requirement IDs you implemented or changed.

Rules:
- Requirement IDs are stable. Never renumber them. Deprecate by marking `Status: deprecated` and adding a replacement.
- A requirement must be testable. If you cannot describe how to check it, rewrite it until you can.
- Do not write code for requirements marked `Status: open`. Those are waiting on `specs/open-questions.md`.

---

## 5. Ambiguity and unknowns

- Do **not** invent AWS resource IDs, account numbers, IP addresses, credentials, or endpoints. Use Terraform outputs, variables, or placeholders that are clearly marked (`<TODO: ...>`).
- Do **not** invent financial values, extraction results, or confidence scores. Extracted values must come from the OCR provider or be `null`.
- If a requirement depends on a sandbox fact that has not been verified (for example, whether Textract is allowed), implement the defined fallback, mark the item in `specs/open-questions.md`, and say so.
- If you must choose between reasonable options that the specs do not decide, choose the simplest option that satisfies the spec, record it as a new ADR file in `specs/adr/` (`ADR-NNN-<slug>.md`), and mention it in your final report. The user can redirect you.

---

## 6. Architecture in one paragraph

Static frontend on **S3 + CloudFront**. Browsers call a **REST API** through an **Application Load Balancer**. Both the API and the **worker** run on the same **EC2 Auto Scaling Group** (private subnets, no public IPs). The API writes uploaded files to **S3**, metadata and job state to **DynamoDB**, and users and sessions to **RDS MySQL** (Single-AZ). The worker polls DynamoDB for pending jobs, downloads the file from S3, calls the **Receipt Extraction Engine** (a pure Python package with no AWS dependency), persists the result in DynamoDB, and publishes a terminal-state notification to **SNS**. **CloudWatch** alarms watch EC2, ALB, and RDS. **CloudTrail** records activity. Details: `specs/01-architecture.md`.

---

## 7. Repository layout

```
AGENTS.md                    This file
README.md                    Human-facing summary
specs/                       Specifications (source of truth for implementation)
specs/adr/                   Architecture decision records, one file per decision
docs/                        Technical documentation for humans (architecture, data justification, deployment guide)
infra/terraform/             Terraform root + modules (IaC)
infra/terraform/modules/     One module per AWS capability (see specs/03)
app/receipt_engine/          Python package: Receipt Extraction Engine (NO AWS imports)
app/worker/                  Python package: job poller + AWS adapters (S3, DynamoDB, SNS)
app/api/                     Python package: FastAPI REST API + SQL migrations
app/frontend/                Static HTML/CSS/JS (no build step)
scripts/                     Packaging, deployment helpers, smoke test, AWS sandbox check
skills/                      Agent skills as plain markdown (any agent can follow them)
samples/receipts/            Synthetic sample documents and expected outputs (never real receipts)
tests/                       Cross-component tests (end-to-end with mocks) — component unit tests live in each package
```

Ownership boundaries:
- `receipt_engine` must **not** import `boto3`, `fastapi`, `sqlalchemy`, or anything AWS/DB/HTTP-related.
- `worker` must **not** import `fastapi` or the API package.
- `api` must **not** import `worker`. They share data only through DynamoDB/RDS schemas in `specs/07-data-model.md`.
- `frontend` talks to the API only through the documented REST contract in `specs/04-api.md`.

---

## 8. Commands (the Makefile is the single entry point)

The `Makefile` at the repository root exposes these targets. Create them if missing. Targets are specified in `specs/10-testing-and-acceptance.md`.

| Target | Purpose |
|---|---|
| `make setup` | Create a uv workspace environment and install locked dependencies |
| `make lint` | `ruff check` + `ruff format --check` on Python; `terraform fmt -check -recursive` on Terraform |
| `make typecheck` | `mypy` on `app/receipt_engine`, `app/worker`, `app/api` |
| `make test` | All unit and contract tests (no AWS calls, no network) |
| `make tf-validate` | `terraform init -backend=false` + `terraform validate` |
| `make tf-plan` | `terraform plan` against the sandbox (read-only) |
| `make package` | Build the release artifact `dist/docuprocess-<version>.tar.gz` |
| `make smoke` | End-to-end smoke test against a deployed environment (needs `SMOKE_BASE_URL`) |

Never run `make tf-apply` or `terraform destroy` without explicit user approval in the current conversation. They create or delete billable resources.

---

## 9. Code standards

**Python (3.12):**
- Type hints on all public functions and class attributes. `mypy --strict` must pass on `receipt_engine`.
- Money is always `decimal.Decimal`. Never `float` for amounts. Serialize money as strings with two decimals (`"119000.00"`).
- Dates are `datetime.date` internally; serialized as ISO 8601 `YYYY-MM-DD`. Timestamps are UTC ISO 8601 with `Z`.
- Errors are typed exceptions defined in each package (no bare `Exception`, no string-matching error messages).
- Logging: `logging` module, structured key=value fields. **Never log document content, raw OCR text, names, NIT values, emails, or amounts.** Log IDs, codes, counts, and timings only.
- No `print` in library code.
- Format and lint with `ruff`. Keep functions small and single-purpose.

**Terraform:**
- Every module has `variables.tf` (with `description` and `type` on every variable), `outputs.tf`, and `main.tf`.
- Resource names use the prefix `docuprocess-` (see `specs/03-infrastructure.md` for the naming scheme).
- Every resource is tagged with the common tags defined in `specs/03-infrastructure.md`.
- No hard-coded account IDs, ARNs, or IPs. Use data sources or variables.
- Never reference IAM roles to create them. Only the pre-existing instance profile is allowed (see `specs/02`).

**General:**
- Small, focused changes. One requirement group per change when possible.
- No dead code, no commented-out code, no TODO without a spec or open-question ID.
- Dependencies are pinned in `pyproject.toml` (Python) and `.terraform.lock.hcl` (Terraform, committed).

---

## 10. Security rules (non-negotiable)

- Never commit secrets, `.env` files, `*.tfstate*`, `.terraform/`, real `.tfvars` with secrets, or AWS credentials.
- Never commit real receipts, invoices, or personal data. Samples in `samples/` must be synthetic and labeled as such.
- Passwords are hashed with Argon2id. Session tokens are random, returned once, and stored only as a SHA-256 hash.
- The database is not publicly accessible. EC2 instances have no public IP and no SSH port. Operators use SSM Session Manager.
- Do not disable TLS verification or broaden security groups "temporarily".

---

## 11. Git and delivery rules

- Work on a feature branch unless the user says otherwise. Never commit directly to `main` without asking.
- **Do not commit or push unless the user asks.** The user will push the harness themselves when ready.
- **Commit messages follow Conventional Commits:** `<type>(<scope>): <summary>`. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`. Scope is the area touched, for example `feat(engine): ...`, `fix(api): ...`, `docs(adr): ...`.
- Keep commits simple: the summary is imperative English, lowercase after the colon, no period, at most 72 characters. Put requirement IDs in the body only when useful (for example `Implements ENG-VAL-01..05`). One logical change per commit.
- **Never add co-author or agent attribution to commits or pull requests.** No `Co-Authored-By` trailers, no "Generated with" footers, no AI tool names in messages. This rule overrides any default attribution line.
- Before finishing a task, run `make lint` and `make test` and report the result.

---

## 12. Definition of done (for any task)

A task is done only when all of the following are true:

1. Every requirement ID it claims is implemented and has at least one test or a documented verification step.
2. `make lint`, `make typecheck` (if Python changed), and `make test` pass. Report the exact result.
3. No file violates the security rules in section 10.
4. Specs, decisions, and open questions are updated where behavior or assumptions changed.
5. The final report lists: what changed, requirement IDs covered, verification run, open items.

Work that cannot be verified here (for example a real Textract call in the sandbox) must be reported as **unverified**, not as passing.

---

## 13. Harness hygiene (mandatory)

The harness must stay small and current. Agents keep it that way:

- **Answered question → delete its row** in `specs/open-questions.md`. Write the consequence into the affected spec or ADR. Never leave a closed item in place.
- **Outdated spec or ADR → edit it or delete it.** Never create a file that contradicts an existing one. No `superseded`, `deprecated`, or `old` copies. Git keeps history.
- **New decision → new ADR file** in `specs/adr/`, one decision per file, named `ADR-NNN-<slug>.md`. Architecture facts that are already settled (for example "everything runs on EC2, no Lambda") belong in `specs/adr/` too.
- Do not add files that duplicate information from another file. Link instead.

## 14. Language

- Everything in the repository is written in **English**: code, comments, specs, docs, commit messages, test names, and sample metadata.
- Exceptions: the course brief (`guia_proyecto_final.pdf`) and user-facing UI copy may be in Spanish if specs say so.
- Your replies to the user may be in Spanish if the user writes in Spanish. Repository artifacts are always English.

---

## 15. AWS sandbox access

- The sandbox credentials are temporary and change every lab session. The procedure is in `skills/aws-sandbox/SKILL.md`. Follow it at the start of any session that touches AWS.
- Credentials are stored only in `~/.aws/credentials`. They must never be written to the repository, specs, docs, logs, commits, or reports (`AGENTS.md` section 10).
- Read-only checks: `scripts/aws_sandbox_check.sh`.
- Write actions on AWS need the user's explicit approval for each action (section 8).

**Closing an open question** (applies to `specs/open-questions.md`): before deleting its row, write into the affected spec or ADR the date, the evidence (command or document, and its result, without secrets or account IDs), the decision it led to, and the former ID as `(was Q-NNN)`. The former ID is what lets a future search find the answer. Never delete a row without this record.

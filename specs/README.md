# Specifications — DocuProcess Cloud

These documents are the implementable requirements for the project.
They are written for AI agents first. Humans review them but do not need to write them by hand.

Read `AGENTS.md` first. It defines the workflow and the precedence rules.

---

## 1. Index

| File | Covers | Requirement prefixes |
|---|---|---|
| `00-product.md` | Purpose, scope, user-facing capabilities, rubric mapping | `PRD` |
| `01-architecture.md` | Topology, components, data flow, network layout | `ARC` |
| `02-aws-sandbox-constraints.md` | Hard AWS Academy restrictions every agent must respect | `CON` |
| `03-infrastructure.md` | Terraform modules, naming, tags, scaling, alarms, CloudTrail | `INF` |
| `04-api.md` | REST API contract, auth, sessions, roles | `API` |
| `05-worker.md` | Job lifecycle, claiming, retries, notifications | `WRK` |
| `06-receipt-extraction-engine.md` | Receipt Extraction Engine: stages, normalization, validation, errors | `ENG` |
| `07-data-model.md` | RDS (MySQL) schema and DynamoDB tables | `DAT` |
| `08-frontend.md` | Static web portal | `FE` |
| `09-security-observability.md` | Security controls, secrets, logging, metrics | `SEC`, `OBS` |
| `10-testing-and-acceptance.md` | Test strategy, Makefile targets, smoke and acceptance tests | `TST` |
| `11-deliverables.md` | Documents the course requires us to produce | `DLV` |
| `adr/` | Architecture decision records, one file per decision (`ADR-NNN`). Read before proposing alternatives | — |
| `open-questions.md` | Unresolved items and unverified sandbox facts (`Q-NNN`) | — |
| `answered-questions.md` | Closed questions with the answer and the evidence that produced it | — |
| `templates/feature-spec.md` | Template for new specs | — |

---

## 2. Requirement ID scheme

Format: `<PREFIX>-<GROUP>-<NN>`, for example `ENG-VAL-03`.

- `PREFIX` is the file's prefix from the index.
- `GROUP` is a short uppercase group inside the file (for example `NET`, `VAL`, `AUTH`).
- `NN` is a two-digit sequence, never reused.

Each requirement is written as a single bullet with:
- a normative keyword: **MUST**, **MUST NOT**, **SHOULD**, **MAY** (RFC 2119 meaning);
- a `Status`: `active`, `open` (blocked on an open question), or `deprecated`.

Example:

```
- **ENG-VAL-03** (active) — The engine MUST reject a total amount that is negative and report `VALIDATION_FAILED`.
```

---

## 3. Precedence inside specs

1. A requirement with a normative keyword overrides prose.
2. Tables and examples illustrate; they do not add requirements unless stated.
3. If two requirements conflict, stop and log a `Q-` item in `open-questions.md`.

---

## 4. How specs are kept current

- A change in behavior MUST be reflected in the relevant spec in the same change.
- A new architectural or technical choice MUST get a new file `specs/adr/ADR-NNN-<slug>.md`, one decision per file.
- A new unknown or unverified sandbox fact MUST get a `Q-NNN` entry in `open-questions.md`.
- **When a question is answered, delete its row** from `open-questions.md`. Record the consequence in the affected spec or ADR in the same change. Do not keep a "resolved" status.
- **When a spec or ADR is no longer true, edit it to the current truth or delete it.** Do not add a new file that contradicts an old one. Git history keeps the past.

---

## 5. Glossary

| Term | Meaning |
|---|---|
| Document | An uploaded file (PDF, PNG, JPEG) plus its metadata. Identified by `document_id` (UUID v4). |
| Job | A unit of asynchronous processing for a document. Identified by `job_id` (UUID v4). |
| Engine | The Receipt Extraction Engine package (`app/receipt_engine`). |
| Worker | The background process (`app/worker`) that runs jobs. |
| API | The REST service (`app/api`). |
| Terminal state | A job status from which no further processing happens: `COMPLETED`, `PARTIAL`, `FAILED`. |
| Sandbox | AWS Academy Vocareum account, region `us-east-1`. |
| Instance profile | The sandbox SSM instance profile (name discovered per session, `CON-IAM-03`). The only IAM identity we may use. |

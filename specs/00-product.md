# 00 — Product

## 1. Purpose

DocuProcess Cloud is a SaaS web platform where enterprise users upload documents (receipts and invoices), the platform processes them asynchronously, extracts structured financial data, and notifies users when processing finishes.

This project is graded as a cloud infrastructure exercise (see section 6). The product must work end-to-end, but the primary evaluation target is **infrastructure quality, reproducibility, and correct service integration**.

## 2. Scope

### In scope (version 1)

- User registration, login, logout, and session management.
- Role-based permissions with two roles: `user` and `admin` (`API-AUTH-*`).
- Upload of one document per request: PDF, PNG, or JPEG (`API-DOC-*`).
- Asynchronous processing of each uploaded document by a worker (`WRK-*`).
- Receipt and invoice extraction through the Receipt Extraction Engine (`ENG-*`).
- Viewing the processing history and the extraction result per document (`FE-*`).
- Email notification via SNS when a document reaches a terminal state (`WRK-NOT-*`).
- Fully automated IaC deployment into the AWS Academy Sandbox (`INF-*`).
- Monitoring with CloudWatch alarms and auditing with CloudTrail (`OBS-*`, `INF-AUD-*`).

### Out of scope (version 1)

- Contract, identity-document, or purchase-order extraction (these are future extensions; the engine architecture must not block them).
- Payments, billing, multi-tenant organizations, password reset by email, OAuth/SSO.
- Custom domain names and TLS certificates for custom domains (Route53 is restricted in the sandbox).
- Lambda-based processing (restricted in the sandbox).
- Kubernetes, message brokers (SQS/Kafka/RabbitMQ), or microservices per extraction stage.
- Multi-page documents (see `ENG-VAL-*` page limits).

## 3. Users

| Actor | Description | Capabilities |
|---|---|---|
| Anonymous visitor | Not logged in | Register, log in, view landing page |
| User (`user`) | Authenticated customer | Upload documents, view own documents and their results |
| Administrator (`admin`) | Authenticated operator | Everything a user can do, plus view all documents and change user roles |

## 4. Functional requirements (summary)

Each row maps to detailed requirements in the referenced spec.

| ID | Requirement | Spec |
|---|---|---|
| PRD-F-01 | Users can register with email and password | `API-AUTH-*` |
| PRD-F-02 | Users can log in and log out; sessions expire | `API-AUTH-*` |
| PRD-F-03 | Authenticated users can upload a document | `API-DOC-*` |
| PRD-F-04 | Each upload is processed asynchronously | `WRK-*` |
| PRD-F-05 | The result is stored and viewable with processing status | `API-DOC-*`, `DAT-*`, `FE-*` |
| PRD-F-06 | Terminal state triggers an SNS notification | `WRK-NOT-*` |
| PRD-F-07 | Administrators can list all documents and assign roles | `API-ADM-*` |
| PRD-F-08 | The platform is deployed entirely by IaC | `INF-*` |

## 5. Non-functional requirements (summary)

| ID | Requirement | Target |
|---|---|---|
| PRD-N-01 | Availability of the API tier | ALB + ASG across two Availability Zones, minimum 2 instances |
| PRD-N-02 | Horizontal scaling of processing | ASG target tracking on CPU, max 4 instances per stack |
| PRD-N-03 | Reproducible deployment | One `terraform apply` from an empty sandbox (after prerequisites) |
| PRD-N-04 | Upload size | Max 5 MB per document (see `ENG-VAL-02`) |
| PRD-N-05 | Processing latency | Median under 30 s per single-page receipt once the job is claimed (informational; not a hard SLA) |
| PRD-N-06 | Privacy | No receipt content or personal data in logs (see `SEC-LOG-*`) |

## 6. Course grading mapping

The course rubric (from `guia_proyecto_final.pdf`, section 6) is mapped to spec areas. Use this to prioritize.

| Rubric criterion | Weight | Spec areas | Evidence to produce |
|---|---|---|---|
| Infrastructure as Code | 30% | `INF-*`, `CON-*` | Clean `terraform apply` from empty sandbox; `plan` with zero errors |
| Architecture and service integration | 25% | `ARC-*`, `INF-NET-*`, `INF-CDN-*` | Diagram in `docs/`; network segmentation; CloudFront → S3; ALB → ASG; S3 → DynamoDB → SNS flow |
| Data management and persistence | 20% | `DAT-*`, `D-*` decisions | RDS Single-AZ schema; DynamoDB tables and justification in `docs/` |
| Monitoring, alerts, resilience | 15% | `OBS-*`, `INF-MON-*`, `INF-ASG-*`, `INF-AUD-*` | CloudWatch alarms; ASG scaling policy; CloudTrail trail |
| Documentation and defense | 10% | `DLV-*` | Git repository quality; deployment guide; live demo script |

## 7. Glossary and links

See `specs/README.md` section 5 for terms. Architecture is in `specs/01-architecture.md`.

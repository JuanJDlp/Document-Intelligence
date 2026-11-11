# Architecture

DocuProcess Cloud is a web platform where users upload receipts and invoices. Processing runs asynchronously on EC2. The target deployment is the AWS Academy Sandbox in `us-east-1`.

> **Visual version:** [`architecture.html`](architecture.html) draws the same architecture with AWS icons (`DLV-ARC-04`).
>
> **Status:** This document describes the designed architecture. After the first deployment, re-check every address and name against `terraform output` (see `deployment-guide.md`).

## 1. Diagram: target topology

```mermaid
flowchart TB
    user(["User browser"])

    subgraph AWS["AWS Region us-east-1 (sandbox)"]
        cf["CloudFront<br/>HTTPS, default domain"]
        s3f[("S3 frontend-assets<br/>private, OAC")]

        subgraph VPC["VPC 10.0.0.0/16"]
            subgraph PUB["Public subnets<br/>10.0.101.0/24 (AZ a) · 10.0.102.0/24 (AZ b)"]
                alb["Application Load Balancer<br/>HTTP :80"]
                nat["NAT gateway<br/>(public-a)"]
            end

            subgraph APP["Private app subnets<br/>10.0.1.0/24 (AZ a) · 10.0.2.0/24 (AZ b)"]
                asg["Auto Scaling Group<br/>EC2 t3.micro, min 2, max 4<br/>API :8000 + Worker (systemd)"]
            end

            subgraph DB["Private DB subnets<br/>10.0.11.0/24 (AZ a) · 10.0.12.0/24 (AZ b)"]
                rds[("RDS MySQL 8.0<br/>Single-AZ, db.t3.micro")]
            end

            gw_s3{{"S3 gateway endpoint"}}
            gw_ddb{{"DynamoDB gateway endpoint"}}
        end

        s3u[("S3 uploads")]
        s3a[("S3 artifacts")]
        ddb[("DynamoDB<br/>documents · jobs")]
        sns["SNS<br/>processing-events · ops-alarms"]
        cw["CloudWatch<br/>alarms + dashboard"]
        ct["CloudTrail"]
        s3l[("S3 audit-logs")]
    end

    mail(["Email subscribers"])

    user -->|"HTTPS /"| cf
    user -->|"HTTPS /api/*"| cf
    cf -->|"default behavior, OAC"| s3f
    cf -->|"/api/* over HTTP :80"| alb
    alb -->|"HTTP :8000, health /api/v1/health"| asg
    asg -->|"MySQL :3306"| rds
    asg --> gw_s3 --> s3u
    asg --> gw_ddb --> ddb
    asg -->|"outbound via NAT"| nat --> sns
    asg -.->|"boot: download release"| s3a
    sns --> mail
    cw -->|"alarm action"| sns
    ct --> s3l
```

Notes on the diagram:
- The first private subnet keeps the CIDR of the course illustration. The second AZ subnets are added because the ALB and the Auto Scaling Group require two AZs. See `specs/adr/ADR-004-two-az-subnet-layout.md`.
- Browsers never call the ALB directly. CloudFront routes `/api/*` to it, so the frontend and API are same-origin over HTTPS. See `specs/adr/ADR-030-same-origin-api-via-cloudfront.md`.
- The NAT gateway is single and not highly available (`specs/adr/ADR-005-single-nat-gateway.md`).

## 2. Diagram: upload and processing flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User browser
    participant CF as CloudFront
    participant API as API (EC2)
    participant S3 as S3 uploads
    participant DDB as DynamoDB
    participant W as Worker (EC2)
    participant E as Receipt Engine
    participant OCR as Tesseract (local)
    participant SNS as SNS

    U->>CF: POST /api/v1/documents (multipart)
    CF->>API: forward to ALB → instance
    API->>API: sniff type, check size (max 5 MiB)
    API->>S3: PutObject uploads/{user}/{doc}/{file}
    API->>DDB: put documents item + jobs item (PENDING)
    API-->>U: 202 Accepted {document_id, job_id}

    loop every 5 s (idle 15 s)
        W->>DDB: query gsi_status_available (PENDING, due)
        W->>DDB: conditional update → RUNNING, lease 300 s
    end
    W->>S3: GetObject
    W->>E: process(DocumentInput)
    E->>OCR: OCR single page (pypdfium2 + pytesseract)
    OCR-->>E: lines with confidence
    E-->>W: ExtractionResult (completed / partial / failed)
    W->>DDB: documents.result + mirror status
    W->>DDB: conditional update jobs → terminal
    W->>SNS: Publish {document_id, job_id, status}
    SNS-->>U: email notification

    U->>CF: GET /api/v1/documents/{id} (polling)
    CF->>API: forward
    API->>DDB: GetItem (consistent read)
    API-->>U: status + result
```

## 3. Components

| Component | Technology | Runs on | Responsibility |
|---|---|---|---|
| Frontend | HTML, CSS, vanilla JS | S3 + CloudFront | Login, upload, history, document detail |
| API | Python 3.12, FastAPI, Uvicorn | EC2 (ASG), port 8000 | Auth, sessions, uploads, status queries |
| Worker | Python 3.12 | EC2 (ASG), systemd service | Claims jobs, runs the engine, persists results, publishes notifications |
| Receipt Extraction Engine | Python 3.12 library, no AWS imports, Tesseract OCR | Imported by the worker | Validation, OCR call, extraction, normalization, result validation |
| Relational store | RDS MySQL 8.0, Single-AZ | Private DB subnets | Users, sessions, roles |
| Document store | S3 `uploads` | S3 | Original files |
| NoSQL store | DynamoDB `documents`, `jobs` | DynamoDB | Document metadata, job state and queue, results |
| Notifications | SNS | SNS | Email on terminal job states; alarm notifications |
| Monitoring | CloudWatch | CloudWatch | Alarms on EC2, ALB, RDS; dashboard |
| Audit | CloudTrail | CloudTrail + S3 | API activity record |

Design rules that shape the system (each is an ADR):
- Everything runs on EC2. No Lambda (`ADR-023`).
- The engine is a pure library and never touches AWS (`ADR-011`).
- No message broker. The `jobs` table is the queue (`ADR-010`).
- Only the pre-existing instance profile is used. Terraform creates no IAM resources (`CON-IAM-01`).

## 4. Network summary

| Subnet | CIDR | AZ | Public IP | Used by |
|---|---|---|---|---|
| public-a | 10.0.101.0/24 | a | yes | ALB, NAT gateway |
| public-b | 10.0.102.0/24 | b | yes | ALB |
| app-a | 10.0.1.0/24 | a | no | ASG instances |
| app-b | 10.0.2.0/24 | b | no | ASG instances |
| db-a | 10.0.11.0/24 | a | no | RDS subnet group |
| db-b | 10.0.12.0/24 | b | no | RDS subnet group (required, even for Single-AZ) |

Security groups:

| Group | Inbound | Outbound |
|---|---|---|
| `alb-sg` | TCP 80 from `0.0.0.0/0` | TCP 8000 to `app-sg` |
| `app-sg` | TCP 8000 from `alb-sg` | All |
| `db-sg` | TCP 3306 from `app-sg` | None |

No security group allows SSH. Operators use SSM Session Manager.

## 5. Sandbox constraints that shaped the design

| Constraint | Design response | Reference |
|---|---|---|
| No IAM role creation | Use the pre-existing instance profile only | `CON-IAM-01` |
| RDS Single-AZ only | RDS Single-AZ, accepted risk | `ADR-003` |
| Max 4 instances in the ASG (course brief) | `max_size = 4` | `INF-ASG-01` |
| No custom domains | Default CloudFront and ALB DNS names | `CON-DNS-01` |
| ALB has no certificate | HTTP on the ALB; CloudFront is the HTTPS entry point | `ADR-025`, `ADR-030` |
| Only SSM for shell access | No key pairs, no bastion | `CON-EC2-05` |
| No Textract permission for the instance role | OCR runs locally with Tesseract | `ADR-012` |
| KMS list access only | No customer keys; RDS not encrypted at rest | `ADR-032` |

## 6. Known limitations (accepted)

Recorded in `risks-and-exceptions.md` when that file exists. Summary:
- Single NAT gateway and single-AZ RDS: a zone failure affects processing and the database (`ADR-005`, `ADR-003`).
- ALB traffic is HTTP inside AWS (`ADR-025`).
- The database password is read from SSM at boot (verified: the instance role can call `ssm:GetParameter`).
- RDS storage is not encrypted at rest (`ADR-032`).

# DocuProcess Cloud

Asynchronous processing of synthetic receipts and invoices for Infraestructura III, Universidad ICESI. Users register, sign in, upload a one-page PDF or a PNG/JPEG, and follow the extracted result in the browser.

The application includes a FastAPI API, an independent Tesseract extraction engine, a lease-based background worker and a static frontend. The AWS design uses CloudFront/S3, ALB, private EC2 instances in an Auto Scaling Group, RDS MySQL, DynamoDB and SNS. See [architecture](docs/architecture.md) and [data design](docs/data-justification.md).

## Run locally

Use Ubuntu 24.04 in WSL, Python 3.12, uv, make, Terraform 1.6+ and Tesseract with Spanish/English language data.

```sh
sudo apt-get update
sudo apt-get install -y make python3-venv tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
make setup
make demo
```

Open http://127.0.0.1:8000, register with a synthetic email and upload `samples/receipts/receipt.pdf`. The sample total is COP 119000.00. The local demo runs real Tesseract, temporary SQLite and in-process AWS mocks. All local data resets when the process stops; no email is delivered.

## Verify and package

```sh
make lint
make typecheck
make test          # deterministic OCR and mocked AWS; no live credentials
make test-ocr      # real Tesseract against synthetic PDF, PNG and JPEG
make tf-validate
make package VERSION=1.0.0
```

`uv.lock` fixes dependencies. `make samples` regenerates document inputs only; golden expectations are independently authored. Packaging writes `dist/docuprocess-1.0.0.tar.gz` and `docs/openapi.json`.

## Deploy to AWS

Follow the [deployment guide](docs/deployment-guide.md). Renew temporary credentials in the WSL user's AWS configuration, verify the session and locate the Terraform state before planning. Missing local state does not prove that the sandbox is empty.

AWS writes require explicit operator approval. Bootstrap the `buckets` module, publish the release, deploy the application stack and upload the frontend in that order. The guide distinguishes infrastructure-only startup from a healthy application deployment.

## Repository

| Path | Purpose |
|---|---|
| `app/receipt_engine/` | Validation, OCR adapter, normalization and extraction; independent of AWS, HTTP and databases |
| `app/api/` | Authentication, authorization, upload/history/detail API and locked MySQL migrations |
| `app/worker/` | Conditional claims, leases, retries, atomic result/mirror updates and terminal SNS publication |
| `app/frontend/` | Login, registration, upload, history and detail pages |
| `infra/terraform/` | Modular infrastructure and instance bootstrap |
| `tests/`, component `tests/` | Contract, worker, golden and integration checks |
| `samples/receipts/` | Synthetic documents, fake OCR recordings and independent expectations |
| `scripts/` | Local demo, static guards, release, deployment and smoke helpers |
| `specs/`, `docs/` | Requirements, decisions and operational documentation |

## Verification boundary

The local flow and static Terraform validation are implemented. A current AWS deployment, healthy targets, MySQL migrations/TLS on RDS, effective instance-role permissions, persistence after instance replacement, SNS email, alarms, CloudTrail and scale-out remain **unverified** until the sandbox acceptance checklist is executed. See [risks](docs/risks-and-exceptions.md) and the [demo script](docs/demo-script.md).

Agent instructions: [AGENTS.md](AGENTS.md). Implementable requirements: [specs/README.md](specs/README.md).

# Demonstration script

## Local milestone

1. In Ubuntu/WSL, run make setup, make samples, make test, and make test-ocr.
2. Run make demo and open http://127.0.0.1:8000.
3. Register with a synthetic email and a password with at least 12 characters, a letter and a number. Sign in.
4. Upload samples/receipts/receipt.pdf. The UI shows PENDING, then RUNNING, then a terminal result. A complete extraction contains total 119000.00 and currency COP.
5. Inspect the history and detail views, upload a PNG or JPEG, and sign out. An encrypted PDF or renamed text file must be rejected.
6. Explain that this local milestone uses moto and temporary SQLite; it does not send email or demonstrate AWS permissions. All local data resets when make demo exits.

## Live sandbox milestone — pending verification

After an approved deployment, run make smoke with SMOKE_BASE_URL set to the CloudFront HTTPS URL. Repeat the browser flow and confirm the SNS email subscription before testing notifications. Verify the document and job in DynamoDB and the uploaded object in the private S3 bucket. Do not display credentials, session tokens or document contents in logs.

Show two healthy ALB targets and SSM access without SSH. Generate controlled CPU load only after explicit approval, observe ASG scale-out within the configured maximum, then stop the load. Observe the CloudWatch alarm, SNS operational notification and CloudTrail logging.

Repeat the approved Terraform plan after deployment: expect no infrastructure differences except intentionally managed scaling capacity. A new release must trigger the ASG instance refresh and preserve RDS/DynamoDB/S3 data. Mark these checks unverified until actually executed.

## Observed local verification

| Check | Observed result |
|---|---|
| make setup | Locked workspace installation succeeds on Ubuntu 24.04 / Python 3.12 |
| make lint | Ruff, formatting, Terraform formatting, constraints, frontend and secret guards pass |
| make typecheck | Strict engine check and API/worker checks pass |
| make test | 84 passed; the real-OCR test is deliberately deselected |
| make test-ocr | 1 passed, covering a synthetic PDF, PNG and JPEG with real Tesseract |
| make tf-validate | Configuration valid with the locked providers; no AWS apply |
| make package-check | Version 1.0.0 archive installs in a fresh isolated environment; all packages and SQL migration resources import successfully |
| Browser, normal storage | Register, login, PDF upload, terminal COMPLETED result, COP 119000.00, back navigation and logout pass |
| Browser, sessionStorage blocked | Same flow passes using memory navigation |
| Responsive/detail page | No horizontal overflow at 360 px; no uncaught JavaScript errors in either storage mode |

The suite emits dependency deprecation warnings from Starlette/AnyIO and botocore; these did not fail validation. Synthetic provider confidence values belong to test fixtures only. Browser and real-OCR checks use Tesseract's own confidence data.

Main requirement trace: API-AUTH-01..09, API-DOC-01..10, WRK-STM-02/03, WRK-CLM-01..06, WRK-PRC-01..07, WRK-PER-01..05, WRK-NOT-01..04, ENG-VAL/EXT/NRM/CHK/STS/OUT/LOG and TST-MK-01..08. Live counterparts remain subject to the sandbox checklist.

The operator selected local-only verification. No AWS deployment, instance replacement, cloud scale-out, real SNS email, CloudTrail or alarm result is claimed by this record.

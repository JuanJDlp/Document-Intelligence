# ADR-037: Reproducible local execution and release

- **Status:** Accepted
- **Area:** Tooling / Deployment

Use Python 3.12 and a uv workspace with three independently installable packages. uv.lock pins the complete development graph; package releases also include a requirements.lock exported from it for installation on EC2. Make is the entry point.

The offline demo uses SQLite for identity, moto for S3/DynamoDB/SNS and a separate worker thread with real Tesseract. These are local adapters, not evidence of AWS deployment. Normal tests inject fake OCR; real OCR is a separate check.

Bootstrap creates module.buckets (the CloudFormation stack containing all four buckets), publishes a release, and then performs the full apply with ELB health checks. Release updates are rolled out by replacing instances one at a time (`ADR-039`). MySQL connections explicitly verify TLS with the AWS RDS CA bundle installed at boot.

Requirements: TST-MK-01..13, INF-UD-03..07, INF-ASG-03, SEC-DATA-02.

The worker subprocess receives file bytes, MIME type and document_id. The optional filename is omitted because validation and extraction depend on content, not the name. API uploads still accept and sanitize filenames for display. This minimizes metadata crossing the OCR boundary (WRK-PRC-04).

Golden files assert independently authored stable contract projections: statuses, selected normalized fields, error reasons, required warning codes and structured line items. Timing and real-provider confidence variability are checked separately rather than saved as golden values. Synthetic OCR fixtures never claim real provider evidence (ENG-TST-01/03, TST-DATA-02).

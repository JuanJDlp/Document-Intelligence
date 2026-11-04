# ADR-012: OCR runs locally with Tesseract; Textract is not used

- **Status:** Accepted
- **Area:** Engine / OCR

## Context
Verified 2026-11-03 (was Q-002): the instance role `AmazonSSMRoleForInstancesQuickSetup` has no Textract permission. Its only policies are `AmazonSSMManagedInstanceCore` and an inline `ssm:*` on parameters. Asynchronous Textract also needs a service role we cannot create (`CON-IAM-04`).

## Decision
The OCR provider in v1 is Tesseract, run on the instance with `pytesseract`. PDFs are rasterized with `pypdfium2`. The engine still exposes the `OCRProvider` interface, so another provider can be added later.

## Consequences
- Tesseract output has no structured summary fields. Extraction relies on text heuristics (`ENG-EXT-*`), so quality is lower than Textract `AnalyzeExpense` would give.
- Multi-page PDFs are still rejected (`ENG-VAL-04`).
- The tesseract binary and language data (`spa`, `eng`) must be installed in userData. Verify that the dnf package names exist on Amazon Linux 2023 during the first deploy.

Specs: `06-receipt-extraction-engine.md`, `03-infrastructure.md` (`INF-UD-01`)

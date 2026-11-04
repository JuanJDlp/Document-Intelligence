# ADR-018: Raw OCR text is off by default and never persisted

- **Status:** Accepted
- **Area:** Privacy

## Context
Receipts contain personal and financial data. The course asks for no receipt content in logs. Debugging still needs the source text sometimes.

## Decision
`include_debug_details` defaults to `False`. The worker never sets it. Raw text is not stored in DynamoDB.

## Consequences
- Debugging a bad extraction means re-running locally with the debug flag on sample files.

Specs: `06`, `05`, `09-security-observability.md`

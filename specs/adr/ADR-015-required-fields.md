# ADR-015: Required fields for `completed`

- **Status:** Accepted
- **Area:** Engine

## Context
Receipts often lack a tax ID or a document number. Requiring everything would make most results `partial`.

## Decision
Required: `merchant_name`, `issue_date`, `currency`, `total`. All other fields are optional.

## Consequences
- Optional fields missing never fail a result.

Specs: `06-receipt-extraction-engine.md` (`ENG-CHK-01`)

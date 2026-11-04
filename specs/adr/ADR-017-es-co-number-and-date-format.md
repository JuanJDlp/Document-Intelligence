# ADR-017: Parse numbers and dates with the es-CO convention

- **Status:** Accepted
- **Area:** Engine

## Context
Colombian receipts use `.` as thousands separator and `DD/MM/YYYY` dates.

## Decision
Default locale `es-CO`. `119.000` is 119000. Dates are day-first. Assumptions add warnings (`AMBIGUOUS_AMOUNT_FORMAT`, `DATE_FORMAT_ASSUMED`).

## Consequences
- Money parsing rules are fixed and tested (`ENG-NRM-01`).

Specs: `06-receipt-extraction-engine.md`

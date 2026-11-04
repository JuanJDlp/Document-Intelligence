# ADR-029: `merchant_address` and `customer_id` are always null in v1

- **Status:** Accepted
- **Area:** Engine

## Context
The course lists them as optional. Extracting them is not needed for the demo.

## Decision
Keys present in the output contract, value `null`.

## Consequences
- A stable contract that can be filled later without breaking clients.

Specs: `06-receipt-extraction-engine.md`

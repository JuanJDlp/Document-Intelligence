# ADR-016: A bare `$` is read as COP, with a warning

- **Status:** Accepted
- **Area:** Engine

## Context
`$` is ambiguous between COP and USD. The product targets Colombia.

## Decision
Bare `$` → `COP` (configurable) with warning `CURRENCY_INFERRED`. Explicit codes (`USD`) and `US$` are never overridden.

## Consequences
- Visible in warnings; wrong inferences can be audited.

Specs: `06-receipt-extraction-engine.md` (`ENG-NRM-03`)

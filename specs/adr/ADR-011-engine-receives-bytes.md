# ADR-011: The engine receives bytes; S3 access stays in the worker

- **Status:** Accepted
- **Area:** Engine

## Context
The course requires the engine to be independent of AWS, API, DynamoDB, and SNS.

## Decision
The engine input is `DocumentInput` (bytes plus metadata). The worker reads S3 and builds that input.

## Consequences
- The engine is testable without AWS (`ENG-TST-04`).

Specs: `06-receipt-extraction-engine.md`, `05-worker.md`

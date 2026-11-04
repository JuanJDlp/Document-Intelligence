# ADR-002: Python 3.12 for all application components, FastAPI for the API

- **Status:** Accepted
- **Area:** Application

## Context
The engine, worker, and API share data contracts. Money and date handling must be exact.

## Decision
Python 3.12 for the engine, worker, and API. FastAPI for the REST API, with typed request and response models.

## Consequences
- One language for the core; engine and worker share types.
- Dependencies pinned in `pyproject.toml` with a lock file (`SEC-DEP-01`).

Specs: `04-api.md`, `05-worker.md`, `06-receipt-extraction-engine.md`

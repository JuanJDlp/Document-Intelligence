# ADR-022: Frontend in plain HTML, CSS, and JavaScript, no build step

- **Status:** Accepted
- **Area:** Frontend

## Context
The portal has three pages. A bundler adds a toolchain to maintain and to deploy.

## Decision
No framework and no bundler. Files are uploaded as they are (ADR-007).

## Consequences
- Dynamic text must use `textContent` (`FE-SEC-01`). A static check guards this.

Specs: `08-frontend.md`

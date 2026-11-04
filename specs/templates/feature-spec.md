# Feature spec: <short title>

- **Spec ID prefix:** `<PREFIX>` (from `specs/README.md` index)
- **Status:** draft | active
- **Owner:** <person or agent>
- **Related decisions:** ADR-NNN
- **Related open questions:** Q-NNN (or none)

## 1. Goal

One paragraph: what problem this solves and for whom. No implementation detail.

## 2. Scope

- In scope: …
- Out of scope: …

## 3. Requirements

Each requirement is a single bullet with a normative keyword and a status.

- **<PREFIX>-<GROUP>-01** (active) The system MUST …
- **<PREFIX>-<GROUP>-02** (active) The system MUST NOT …
- **<PREFIX>-<GROUP>-03** (open) … (blocked by Q-NNN)

## 4. Interfaces

Inputs, outputs, error codes, and data shapes. Reference the existing contracts (`04-api.md`, `06-receipt-extraction-engine.md`, `07-data-model.md`) instead of copying them.

## 5. Constraints

Reference `02-aws-sandbox-constraints.md` and any relevant `CON-*` IDs.

## 6. Acceptance

- **<PREFIX>-ACC-01** How to verify requirement 01 (test name, command, or checklist ID).
- Requirements that can only be checked in the sandbox must list the `TST-E2E-*` entry.

## 7. Risks and unknowns

Anything that could change the design. Each item gets a `Q-` entry if it is unresolved.

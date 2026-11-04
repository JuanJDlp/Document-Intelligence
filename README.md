# DocuProcess Cloud

SaaS platform for asynchronous processing of receipts and invoices, deployed on AWS (Infraestructura III, Universidad ICESI).

- **AI agents:** start with [`AGENTS.md`](AGENTS.md), then [`specs/README.md`](specs/README.md).
- **Requirements:** [`specs/`](specs/). Source course brief: `guia_proyecto_final.pdf`.
- **Deliverables for humans:** [`docs/`](docs/) (architecture, data justification, deployment guide, demo script). Written from the deployed system.

## Layout

| Path | Contents |
|---|---|
| `infra/terraform/` | Infrastructure as Code (Terraform modules) |
| `app/receipt_engine/` | Receipt Extraction Engine (pure Python library) |
| `app/worker/` | Background job processor |
| `app/api/` | REST API |
| `app/frontend/` | Static web portal |
| `scripts/` | Packaging, deployment, smoke test, guards |
| `samples/` | Synthetic receipts and expected outputs |

## Prerequisites

- AWS Academy Sandbox (region `us-east-1`) with CLI credentials exported in the shell
- Terraform 1.6+
- Python 3.12 and `uv`
- `make`

## Common commands

```sh
make setup      # install dependencies
make lint       # style and constraint guards
make test       # unit and contract tests (offline)
make tf-validate
make tf-plan    # read-only plan
```

Deployment commands (`deploy`, `publish`, `destroy`, …) are listed in [`specs/10-testing-and-acceptance.md`](specs/10-testing-and-acceptance.md) section 3 and require explicit approval before running.

## Status

Specification phase. Implementation has not started.

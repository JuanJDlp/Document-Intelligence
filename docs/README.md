# Technical documentation

Human-facing documents for DocuProcess Cloud. They describe the system as designed and as deployed. The requirements they rely on are in `specs/`.

| Document | Contents |
|---|---|
| [`architecture.md`](architecture.md) | Deployment diagram, upload and processing sequence, components, network layout, sandbox constraints that shaped the design |
| [`architecture.html`](architecture.html) | Visual version of the architecture with AWS icons (topology, flow, job lifecycle, bootstrap, security groups, data placement). Open it in a browser; it works offline |
| [`data-justification.md`](data-justification.md) | Why RDS holds users and sessions, why DynamoDB holds documents, jobs, and results, and why there is no SQS |
| [`deployment-guide.md`](deployment-guide.md) | Step-by-step deployment from an empty sandbox, expected output per step, troubleshooting |

Also available: [risks and verification boundaries](risks-and-exceptions.md), [demonstration script](demo-script.md), and the generated [OpenAPI contract](openapi.json). Local validation does not establish a current AWS deployment.

Architecture decisions are recorded one per file in `specs/adr/`.

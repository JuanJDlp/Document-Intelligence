# ADR-033: Data access for the instance role uses resource-based policies

- **Status:** Accepted
- **Area:** Security / Data

## Context
Verified 2026-11-03 (was Q-001). The instance role `AmazonSSMRoleForInstancesQuickSetup` has no identity-based permission for S3, DynamoDB, SNS, or SQS. We cannot create roles or policies (`CON-IAM-01`).

Tests from an instance, through SSM Run Command:
- A bucket policy with `Principal.AWS` set to the role ARN allowed `s3 cp` and `list-objects-v2`.
- An SNS topic policy with the role ARN allowed `sns publish`.
- A DynamoDB resource policy with the role ARN allowed `put-item` and `get-item`.
- A policy naming the account root (`arn:aws:iam::<account>:root`) did NOT grant access.

## Decision
Every bucket, table, and topic used by the application carries a resource policy that names the instance role ARN. The ARN is built from the account ID, not read from IAM.

## Consequences
- Terraform adds the policies in the storage, DynamoDB, and messaging modules (`INF-RPOL-*`).
- If the policy is removed, the application loses access immediately.
- Access depends on the lab allowing resource policies. It was verified once, on 2026-11-03.

Specs: `03-infrastructure.md` section 17, `02-aws-sandbox-constraints.md` section 0.1

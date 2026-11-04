# ADR-034: The launch template maps the root volume explicitly as gp2

- **Status:** Accepted
- **Area:** Compute

## Context
Verified 2026-11-03 (was Q-013). The lab role has an explicit deny on `ec2:RunInstances` for volumes of type `gp3`. The default root volume of the Amazon Linux 2023 AMI is `gp3`, so a launch without an explicit mapping fails. Dry-runs with `gp2` (encrypted or not, 8 or 20 GB, with or without a KMS alias) are allowed. An Auto Scaling Group with a `gp2` root mapping reached `InService` and `Healthy`.

## Decision
The launch template sets `BlockDeviceMappings` for `/dev/xvda`: type `gp2`, 20 GB, encrypted.

## Consequences
- Any future launch template must keep this mapping. Removing it breaks instance launch.
- EBS encryption uses the default AWS-managed key, so it works without KMS management (`CON-KMS-01`).

Specs: `03-infrastructure.md` section 8, `02-aws-sandbox-constraints.md` section 0.1

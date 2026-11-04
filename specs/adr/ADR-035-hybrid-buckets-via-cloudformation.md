# ADR-035: S3 buckets are created by CloudFormation; policies stay in Terraform

- **Status:** Accepted
- **Area:** Infrastructure / Tooling

## Context
Verified 2026-11-03 (see `answered-questions.md`). The lab denies `s3:GetBucketObjectLockConfiguration` to the lab role with an explicit deny. The AWS provider reads that configuration on every refresh of an `aws_s3_bucket`, in provider versions 3.76.1, 4.67.0, 5.100.0 and 6.71.0. Terraform cannot manage `aws_s3_bucket` in this sandbox.

CloudFormation creates an `AWS::S3::Bucket` without that read. A test stack reached `CREATE_COMPLETE` and was deleted.

## Decision
- `infra/terraform/modules/buckets` creates one `aws_cloudformation_stack` from `templates/buckets.yaml`. The template creates four buckets: uploads, artifacts, frontend, and audit logs. Each has its public access block, SSE-S3 encryption, and (audit only) a 30-day lifecycle.
- Terraform owns everything that is not bucket creation: bucket policies (`modules/bucket_policies`, `modules/frontend`, `modules/audit`).
- Terraform reads bucket names and ARNs from the stack outputs.
- `scripts/check_constraints.sh` fails if Terraform declares `aws_s3_bucket`.
- `make tf-destroy` empties the buckets (`scripts/empty_buckets.sh`) before destroying the stack, because CloudFormation cannot delete buckets that contain objects.

## Consequences
- Two tools manage one stack of resources. The boundary is fixed: CloudFormation for bucket creation, Terraform for everything else.
- Changing a bucket's intrinsic settings (name, encryption, public access block) happens in the template, not in Terraform.
- Deleting the environment requires emptying the buckets first. The Makefile does this.
- Outside this sandbox, the normal `aws_s3_bucket` resource should be used again. Revisit this ADR when the lab permissions change.

Specs: `03-infrastructure.md` section 5, `02-aws-sandbox-constraints.md` section 0.1

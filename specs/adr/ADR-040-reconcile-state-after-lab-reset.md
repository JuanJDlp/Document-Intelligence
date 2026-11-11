# ADR-040: Reconcile the local Terraform state with the lab before deploying

- **Status:** Accepted
- **Area:** Infrastructure / Operations

## Context
Verified 2026-11-11. The local `terraform.tfstate` stays on the operator's machine (no remote backend in the sandbox), but each lab session can reset the account. After a reset:

- The state still lists about 64 resources (VPC, ASG, RDS, buckets) that no longer exist.
- Three resources survived the reset: the SSM parameter `/<project>/<environment>/db/password`, the CloudFront origin access control `<name>-frontend-oac` and the CloudFront response headers policy `<name>-security-headers`. With a fresh state, `make up` failed with `ParameterAlreadyExists`, `OriginAccessControlAlreadyExists` and `ResponseHeadersPolicyAlreadyExists`.

## Decision
`make up` runs `make prepare-state` (`scripts/prepare_state.sh`, `TST-MK-17`) first:

1. The single instance profile whose name contains `SsmRoleInstanceProfile` is written to the git-ignored `terraform.tfvars` as `instance_profile_name` (the file is copied from the example if missing). The name changed between the lab sessions of 2026-11-10 and 2026-11-11. With zero or several matches the script stops and the operator sets it by hand.
2. If the VPC recorded in the state does not exist in the account, the state belongs to an earlier lab session. It is moved to `terraform.tfstate.stale-<UTC timestamp>.backup`, never deleted.
3. Each of the three survivors that exists in the account but not in the state is imported with `terraform import`.

The script only reads AWS (including the IAM list call the aws-sandbox skill already uses; Terraform itself still makes no IAM calls, `CON-IAM-02`) and changes local files. The VPC is the sentinel because it is created first and destroyed last, and a reset removes it.

## Consequences
- `make up` works from a clean account, from a reset lab with a stale state, and on a re-run with a current state.
- An imported SSM parameter keeps its old value until `deploy` overwrites it with the password Terraform generates for RDS (observed 2026-11-11: the plan showed it as one in-place change).
- If a future reset keeps another resource, add it to the script and to this ADR.

Specs: `10-testing-and-acceptance.md` (`TST-MK-15`, `TST-MK-17`), `docs/deployment-guide.md`.

#!/usr/bin/env bash
# Static guard for the AWS Academy sandbox constraints (specs/02, TST-CON-01).
# Fails when Terraform uses a resource type or setting the sandbox forbids.
set -euo pipefail

TF_DIR="${1:-infra/terraform}"
fail=0

check() {
  local pattern="$1" message="$2"
  if grep -rEn --include='*.tf' --include='*.tftpl' "$pattern" "$TF_DIR" >/tmp/check_constraints.hits 2>/dev/null && [ -s /tmp/check_constraints.hits ]; then
    echo "FORBIDDEN: $message"
    sed 's/^/  /' /tmp/check_constraints.hits
    fail=1
  fi
}

check 'resource[[:space:]]+"aws_iam_(role|policy|role_policy|role_policy_attachment|instance_profile)"' "IAM resources are not allowed (CON-IAM-01)"
check 'data[[:space:]]+"aws_iam_role"' "IAM reads by Terraform are not allowed (CON-IAM-02)"
check 'resource[[:space:]]+"aws_lambda_' "Lambda is not used (ADR-023)"
check 'resource[[:space:]]+"aws_(route53|api_gateway|ecs|eks|acm_certificate|kms_key)' "Route53, API Gateway, ECS, EKS, ACM and KMS keys are not used"
check 'resource[[:space:]]+"aws_key_pair"' "SSH key pairs are not allowed (CON-EC2-05)"
check 'key_name[[:space:]]*=' "SSH key names are not allowed (CON-EC2-05)"
check 'multi_az[[:space:]]*=[[:space:]]*true' "Multi-AZ RDS is not allowed (CON-RDS-02)"
check 'publicly_accessible[[:space:]]*=[[:space:]]*true' "Public RDS is not allowed (CON-RDS-05)"
check 'resource[[:space:]]+"aws_s3_bucket"[[:space:]]+"' "S3 buckets are created by CloudFormation, not by aws_s3_bucket (ADR-035)"
check 'volume_type[[:space:]]*=[[:space:]]*"gp3"' "gp3 volumes are denied for the lab role (ADR-034)"

if [ "$fail" -ne 0 ]; then
  echo "check_constraints: FAILED"
  exit 1
fi
echo "check_constraints: OK"

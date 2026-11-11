#!/usr/bin/env bash
# Makes the local Terraform state match the sandbox before `make up` (TST-MK-17, ADR-040).
# 1. A lab reset deletes the VPC but not the local state: if the VPC in the state no longer
#    exists, the state belongs to an earlier lab session and is moved aside as a backup.
# 2. A lab reset keeps some resources (SSM parameters, CloudFront OAC and response headers
#    policies). Each one that exists in the account but not in the state is imported.
# 3. The SSM instance profile name changes per lab session: it is discovered and written to
#    the git-ignored terraform.tfvars (created from the example if missing).
set -euo pipefail
dir=infra/terraform
tf="terraform -chdir=$dir"

vars_file="$dir/terraform.tfvars"
profiles="$(aws iam list-instance-profiles --query "InstanceProfiles[?contains(InstanceProfileName, 'SsmRoleInstanceProfile')].InstanceProfileName" --output text)"
if [ -z "$profiles" ] || [ "$(wc -w <<<"$profiles")" -ne 1 ]; then
  echo "prepare_state: expected exactly one SsmRoleInstanceProfile, found: ${profiles:-none}. Set instance_profile_name in $vars_file by hand." >&2
  exit 1
fi
[ -f "$vars_file" ] || cp "$dir/terraform.tfvars.example" "$vars_file"
sed -i "s|^instance_profile_name *=.*|instance_profile_name = \"$profiles\"|" "$vars_file"
echo "prepare_state: instance profile $profiles"

$tf init -input=false >/dev/null

state_file="$dir/terraform.tfstate"
if [ -s "$state_file" ]; then
  vpc_id="$($tf state show -no-color module.network.aws_vpc.this 2>/dev/null | sed -n 's/^ *id *= *"\(vpc-[0-9a-f]*\)"$/\1/p' || true)"
  if [ -n "$vpc_id" ] && aws ec2 describe-vpcs --vpc-ids "$vpc_id" >/dev/null 2>&1; then
    echo "prepare_state: state matches the sandbox"
  else
    backup="$state_file.stale-$(date -u +%Y%m%dT%H%M%SZ).backup"
    mv "$state_file" "$backup"
    echo "prepare_state: state is from an earlier lab session, moved to $backup"
  fi
fi

name="$(echo 'local.name' | $tf console | tr -d '"')"
in_state="$($tf state list 2>/dev/null || true)"

import_if_present() {
  local address="$1" id="$2"
  if [ -z "$id" ] || [ "$id" = "None" ]; then
    return
  fi
  if grep -qxF "$address" <<<"$in_state"; then
    return
  fi
  echo "prepare_state: importing leftover $address"
  $tf import -input=false "$address" "$id" >/dev/null
}

param="$(echo '"/${var.project}/${var.environment}/db/password"' | $tf console | tr -d '"')"
param_found="$(aws ssm describe-parameters --parameter-filters "Key=Name,Values=$param" --query 'Parameters[0].Name' --output text)"
import_if_present module.database.aws_ssm_parameter.db_password "$param_found"

oac_id="$(aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='$name-frontend-oac'].Id | [0]" --output text)"
import_if_present module.frontend.aws_cloudfront_origin_access_control.frontend "$oac_id"

policy_id="$(aws cloudfront list-response-headers-policies --type custom --query "ResponseHeadersPolicyList.Items[?ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name=='$name-security-headers'].ResponseHeadersPolicy.Id | [0]" --output text)"
import_if_present module.frontend.aws_cloudfront_response_headers_policy.security "$policy_id"

echo "prepare_state: done"

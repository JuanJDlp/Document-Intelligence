#!/usr/bin/env bash
# Read-only check of the AWS Academy sandbox session.
# Prints the caller ARN, the configured region, and OK/DENIED per service probe.
# Never prints credentials. Never creates or modifies resources.
set -uo pipefail
export AWS_PAGER=""

REGION="$(aws configure get region 2>/dev/null || true)"
REGION="${REGION:-us-east-1}"

echo "== identity"
if ! ARN="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)"; then
  echo "SESSION INVALID OR EXPIRED: ask the user to restart the lab and paste new credentials."
  exit 2
fi
echo "arn: ${ARN}"
echo "region: ${REGION}"

echo "== read-only probes (run as the lab role, not as the EC2 instance profile)"
probe() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'OK      %s\n' "$name"
  else
    printf 'DENIED  %s\n' "$name"
  fi
}
probe "ec2 describe-vpcs"                    aws ec2 describe-vpcs --region "$REGION" --max-items 1
probe "autoscaling describe-auto-scaling-groups" aws autoscaling describe-auto-scaling-groups --region "$REGION" --max-items 1
probe "elbv2 describe-load-balancers"        aws elbv2 describe-load-balancers --region "$REGION"
probe "rds describe-db-instances"            aws rds describe-db-instances --region "$REGION" --max-items 1
probe "dynamodb list-tables"                 aws dynamodb list-tables --region "$REGION" --max-items 1
probe "s3api list-buckets"                   aws s3api list-buckets
probe "sns list-topics"                      aws sns list-topics --region "$REGION"
probe "sqs list-queues"                      aws sqs list-queues --region "$REGION"
probe "cloudfront list-distributions"        aws cloudfront list-distributions
probe "cloudtrail describe-trails"           aws cloudtrail describe-trails --region "$REGION"
probe "ssm describe-parameters"              aws ssm describe-parameters --region "$REGION" --max-results 1
probe "iam list-instance-profiles"           aws iam list-instance-profiles --max-items 1
probe "lambda list-functions"                aws lambda list-functions --region "$REGION" --max-items 1

# Dry-run probes: validate authorization without creating anything.
# DryRunOperation means allowed; UnauthorizedOperation means denied.
dryrun_probe() {
  local name="$1"; shift
  local out
  out="$("$@" 2>&1)"
  if grep -q DryRunOperation <<<"$out"; then
    printf 'OK      %s (dry-run)\n' "$name"
  elif grep -q UnauthorizedOperation <<<"$out"; then
    printf 'DENIED  %s (dry-run)\n' "$name"
  else
    printf 'UNKNOWN %s (dry-run)\n' "$name"
  fi
}
dryrun_probe "ec2 create-vpc"                aws ec2 create-vpc --cidr-block 10.99.0.0/16 --dry-run --region "$REGION"
dryrun_probe "ec2 create-internet-gateway"   aws ec2 create-internet-gateway --dry-run --region "$REGION"
dryrun_probe "ec2 allocate-address"          aws ec2 allocate-address --domain vpc --dry-run --region "$REGION"
probe "iam get-role (instance role)"         aws iam get-role --role-name AmazonSSMRoleForInstancesQuickSetup

#!/usr/bin/env bash
# Waits until the API target group has as many healthy targets as the ASG minimum (TST-MK-15).
set -euo pipefail
tf="terraform -chdir=infra/terraform"
target_group="$($tf output -raw target_group_arn)"
asg="$($tf output -raw asg_name)"
wanted="$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$asg" --query 'AutoScalingGroups[0].MinSize' --output text)"
timeout_seconds="${WAIT_TIMEOUT_SECONDS:-1200}"
deadline=$(( $(date +%s) + timeout_seconds ))

echo "Waiting for $wanted healthy targets (timeout ${timeout_seconds}s). First boot installs packages and takes several minutes."
while true; do
  states="$(aws elbv2 describe-target-health --target-group-arn "$target_group" --query 'TargetHealthDescriptions[].TargetHealth.State' --output text)"
  healthy="$(tr -s '[:space:]' '\n' <<<"$states" | grep -c '^healthy$' || true)"
  echo "$(date +%H:%M:%S) healthy=$healthy/$wanted states: ${states:-none}"
  if (( healthy >= wanted )); then
    break
  fi
  if (( $(date +%s) >= deadline )); then
    echo "Timed out. See the troubleshooting table in docs/deployment-guide.md (Targets unhealthy)."
    exit 1
  fi
  sleep 20
done
echo "Ready: https://$($tf output -raw cloudfront_domain_name)"

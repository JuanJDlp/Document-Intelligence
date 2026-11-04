#!/usr/bin/env bash
# Empties the sandbox buckets so the CloudFormation stack that owns them can be deleted (ADR-035).
# Sandbox only: deletes every object and every version of the listed buckets.
set -euo pipefail

BUCKETS=$(terraform -chdir=infra/terraform output -json 2>/dev/null | python3 -c '
import json,sys
o=json.load(sys.stdin)
for k in ("uploads_bucket_name","artifacts_bucket_name","frontend_bucket_name","audit_logs_bucket_name"):
    if k in o: print(o[k]["value"])
' 2>/dev/null || true)

if [ -z "$BUCKETS" ]; then
  echo "no bucket names in outputs; nothing to empty"
  exit 0
fi

for b in $BUCKETS; do
  echo "emptying $b"
  aws s3 rm "s3://$b" --recursive >/dev/null 2>&1 || true
  # Remove versions and delete markers if versioning ever left any behind.
  aws s3api list-object-versions --bucket "$b" --output json 2>/dev/null \
    | python3 -c '
import json,sys
d=json.load(sys.stdin); items=(d.get("Versions") or [])+(d.get("DeleteMarkers") or [])
for i in items: print(i["Key"]+"\t"+i["VersionId"])
' \
    | while IFS=$'\t' read -r key vid; do
        aws s3api delete-object --bucket "$b" --key "$key" --version-id "$vid" >/dev/null
      done
done
echo "buckets emptied"

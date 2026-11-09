#!/usr/bin/env bash
set -euo pipefail
bucket="$(terraform -chdir=infra/terraform output -raw frontend_bucket_name)"
distribution="$(terraform -chdir=infra/terraform output -raw cloudfront_distribution_id)"
aws s3 sync app/frontend/ "s3://$bucket/" --cache-control no-cache --only-show-errors
aws cloudfront create-invalidation --distribution-id "$distribution" --paths '/*' --query Invalidation.Status --output text

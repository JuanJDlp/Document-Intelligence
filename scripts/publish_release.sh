#!/usr/bin/env bash
set -euo pipefail
version="${1:?Usage: publish_release.sh VERSION}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]] || { echo "Invalid version"; exit 1; }
artifact="dist/docuprocess-$version.tar.gz"
test -f "$artifact"
bucket="$(terraform -chdir=infra/terraform output -raw artifacts_bucket_name)"
aws s3 cp "$artifact" "s3://$bucket/releases/$version/docuprocess-$version.tar.gz" --only-show-errors
echo "Release uploaded."

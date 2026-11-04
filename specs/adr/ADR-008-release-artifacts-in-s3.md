# ADR-008: Release tarball in an S3 bucket, downloaded by userData

- **Status:** Accepted
- **Area:** Delivery

## Context
Instances must get the application code at boot. Cloning from Git would need credentials on each instance.

## Decision
`make package` builds `dist/docuprocess-<version>.tar.gz`. `scripts/publish_release.sh` uploads it to the `artifacts` bucket. userData downloads that exact version.

## Consequences
- No Git credentials on instances. Reproducible releases.
- Bootstrap order matters: the artifacts bucket must exist before the ASG (`03` section 16).

Specs: `03-infrastructure.md`

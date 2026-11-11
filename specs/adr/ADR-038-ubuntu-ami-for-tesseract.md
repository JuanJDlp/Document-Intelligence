# ADR-038: Ubuntu 24.04 AMI for the application instances

- **Status:** Accepted
- **Area:** Infrastructure / Compute

## Context
Verified 2026-11-10 during the first full deployment. The user data on Amazon Linux 2023 failed at its first step with `dnf: No match for argument: tesseract` (also `tesseract-langpack-spa`, `tesseract-langpack-eng`). AL2023 does not ship Tesseract and does not support EPEL. Because the script runs with `set -e`, the release was never installed, the API never started, and every ALB target stayed unhealthy (CloudFront answered `502`).

Tesseract is the only OCR provider in v1 (`ADR-012`). The alternatives were compiling Tesseract and Leptonica at boot (20+ minutes per `t3.micro`, risk of running out of memory) or downloading prebuilt binaries from conda-forge at boot (third-party dependency, not tested).

Evidence (2026-11-10, lab role, `us-east-1`):
- `aws ec2 describe-images --owners amazon --filters Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*` returns the current Ubuntu 24.04 image. Canonical's Ubuntu images carry the owner alias `amazon`, so the `CON-EC2-04` filter still applies unchanged.
- `aws ec2 run-instances --dry-run` with that image, `t3.micro` and a 20 GB `gp2` root volume returns `DryRunOperation` (allowed).

## Decision
- The launch template uses the most recent Ubuntu Server 24.04 LTS (`noble`, `amd64`) image, resolved with `data "aws_ami"`, `owners = ["amazon"]`, name `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*`.
- The root device name comes from the AMI (`root_device_name`), not from a literal. It is still mapped as `gp2` (`ADR-034`).
- User data installs `tesseract-ocr`, `tesseract-ocr-spa` and `tesseract-ocr-eng` with `apt-get`. Ubuntu images do not include AWS CLI v2, so user data installs it from the official AWS installer before it calls SSM and S3.
- The SSM agent is preinstalled on Ubuntu images, so Session Manager access does not change (`CON-EC2-05`).

## Consequences
- Boot downloads the AWS CLI and the apt packages through the NAT gateway; the first boot takes a few minutes longer.
- Python is still provided by `uv python install 3.12`, so the OS Python version does not matter.
- Specs: `02-aws-sandbox-constraints.md` (`CON-EC2-04`), `03-infrastructure.md` (`INF-EC2-01`, `INF-UD-01`), `ADR-012`.

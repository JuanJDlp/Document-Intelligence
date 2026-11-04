# Deployment guide

This guide deploys DocuProcess Cloud from an empty AWS Academy Sandbox to a working system. Each step says what to run, what you should see, and what to do if it fails.

> **Status:** Draft. The Makefile targets and scripts are specified in `specs/10-testing-and-acceptance.md` but not implemented yet. Commands marked **(after implementation)** do not exist until the code is written. Items marked **(verify)** depend on open questions in `specs/open-questions.md`.

## 0. Prerequisites

| Item | Check |
|---|---|
| AWS Academy Sandbox started, region `us-east-1` | Lab console shows the region |
| CLI credentials exported in your shell (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) | `aws sts get-caller-identity` returns an ARN |
| Instance profile name discovered by the `aws-sandbox` skill | `aws iam list-instance-profiles` shows a name containing `SsmRoleInstanceProfile` |
| Terraform 1.6 or newer | `terraform version` |
| Python 3.12 and `uv` | `python3.12 --version`, `uv --version` |
| `make` | `make --version` |
| An email address you can read, for SNS confirmation | You will receive one confirmation email per topic |

Sandbox rules that affect this guide are summarized in `specs/02-aws-sandbox-constraints.md`. Do not change instance types or database classes outside the allowed ranges.

## 1. Clone and configure

```sh
git clone <repository-url> docuprocess-cloud
cd docuprocess-cloud
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Edit `infra/terraform/terraform.tfvars` and set at least:

```hcl
alert_email             = "you@example.com"
release_version         = "1.0.0"
instance_profile_name   = "<discovered by skills/aws-sandbox>"
```

Do not commit this file. It is git-ignored.

**Expected:** `terraform.tfvars` exists and is not tracked by Git (`git status` does not list it).

## 2. Install dependencies and run local checks

```sh
make setup
make lint
make typecheck
make test
```

**(after implementation)**

**Expected:** all four commands exit with status 0. If `make test` fails, do not deploy. Fix the failing tests first.

## 3. Validate the Terraform configuration

```sh
make tf-validate
```

**(after implementation)** This runs `terraform init -backend=false` and `terraform validate`. It makes no AWS calls.

**Expected:** `Success! The configuration is valid.`

## 4. Review the plan

```sh
make tf-plan
```

**(after implementation)** This is read-only. Read the output and check:
- No IAM role, policy, or instance profile is created (`CON-IAM-01`).
- No Lambda, Route53, KMS key, or key pair is created (`02` section 0).
- RDS shows `multi_az = false` and `publicly_accessible = false`.
- ASG shows min 2, max 4.

If the plan includes a forbidden resource, stop. Run `scripts/check_constraints.sh` and fix the Terraform before going on.

## 5. Create the artifacts bucket

The EC2 instances download the release from the artifacts bucket at boot, so the bucket must exist before the Auto Scaling Group.

```sh
make bootstrap-artifacts
```

**(after implementation)** This applies only the storage module (`terraform apply -target=module.storage`). It requires your approval, because it creates billable resources.

**Expected:** the output shows the artifacts bucket name, for example `docuprocess-sandbox-artifacts-<account-id>`.

## 6. Build and publish the release

```sh
make package
make publish
```

**(after implementation)** `make package` builds `dist/docuprocess-<version>.tar.gz` and `docs/openapi.json`. `make publish` uploads the tarball to `releases/<version>/` in the artifacts bucket.

**Expected:** `aws s3 ls s3://<artifacts-bucket>/releases/<version>/` lists the tarball.

## 7. Deploy the full stack

```sh
make deploy
```

**(after implementation)** Runs `terraform apply` with the release version. It takes several minutes, mostly RDS and the CloudFront distribution. It requires your approval.

**Expected:** Terraform ends with `Apply complete!` and prints the outputs (`alb_dns_name`, `cloudfront_domain_name`, and others). The database password is never printed.

## 8. Wait for healthy instances

Open the EC2 console and the target group `docuprocess-sandbox-api`, or run:

```sh
aws elbv2 describe-target-health --target-group-arn <arn>
```

**Expected:** two targets with state `healthy`. Allow 5 to 10 minutes after apply: instances boot, install the release, run migrations, and start the services.

If targets stay `unhealthy`, see troubleshooting **T1** below.

## 9. Confirm the SNS subscriptions

Two confirmation emails arrive at `alert_email`: one for the processing topic and one for the alarms topic. Open each email and click **Confirm subscription**.

**Expected:** `aws sns list-subscriptions-by-topic --topic-arn <arn>` shows `Confirmed` for both. Notifications are not delivered until you confirm.

## 10. Deploy the frontend

```sh
make deploy-frontend
```

**(after implementation)** Uploads `app/frontend/` to the frontend bucket and creates a CloudFront invalidation for `/*`. It requires your approval.

**Expected:** the script prints the CloudFront URL. Open it in a browser. You should see the login page.

The frontend uses the relative path `/api/v1`, so no URL needs to be set in the code (`ADR-030`).

## 11. Run the smoke test

```sh
SMOKE_BASE_URL=https://<cloudfront-domain> make smoke
```

**(after implementation)** The smoke test registers a random user, logs in, uploads a synthetic receipt, waits for a terminal status, checks the result fields, and logs out. It prints only step names and HTTP status codes.

**Expected:** `SMOKE OK` and exit code 0. A job that ends `PARTIAL` or `COMPLETED` is success. `FAILED` on the sample receipt is a failure to investigate.

## 12. Manual checks

Run the checklist in `specs/10-testing-and-acceptance.md` section 6 (`TST-E2E-01` to `TST-E2E-15`) and record the results. The items that need your eyes:

1. Register and log in through the browser.
2. Upload a PDF receipt. Watch the status change on the detail page.
3. Receive the SNS email for that document.
4. Upload a 6 MB file. Expect a `413` error message.
5. Open an SSM session to an instance: `aws ssm start-session --target <instance-id>`. Confirm there is no SSH port.
6. Run `terraform apply` again. Expect **no changes**.

## 13. Teardown

```sh
make destroy
```

**(after implementation)** Prints the destroy plan and asks for approval. The S3 buckets are emptied and deleted because `force_destroy` is set for sandbox buckets.

**Expected:** `Destroy complete!`. Check the RDS console afterwards: the instance should be gone, and no snapshot is kept (`skip_final_snapshot = true`).

## Troubleshooting

### T1. ALB targets are unhealthy

- **Symptom:** the target group shows `unhealthy` or `draining`.
- **Likely cause:** the API failed to start or cannot reach RDS or DynamoDB.
- **Check:** connect with SSM and run:
  ```sh
  sudo tail -n 100 /var/log/docuprocess-bootstrap.log
  sudo journalctl -u docuprocess-api -n 100 --no-pager
  curl -s localhost:8000/api/v1/health
  ```
- **Fix:** if the bootstrap log shows a download error, see **T2**. If the health endpoint returns `503`, check **T4** and **T5**.

### T2. userData cannot download the release

- **Symptom:** bootstrap log shows `AccessDenied` or `NoSuchKey` for the artifacts bucket.
- **Cause:** the release version in `terraform.tfvars` was not published, or the artifacts bucket policy does not name the instance role (`ADR-033`).
- **Fix:** run `make publish` with the same version, or verify the instance profile permissions. If `s3:GetObject` is denied, check the bucket policy (`ADR-033`).

### T11. Launch fails with "not authorized to use launch template"

- **Symptom:** the Auto Scaling Group cannot be created, or instances never launch.
- **Cause:** the launch template uses the `gp3` root volume, which the lab denies (`ADR-034`).
- **Fix:** map the root volume explicitly as `gp2` in the launch template.

### T3. Instances cannot install or reach the internet

- **Symptom:** bootstrap log stops at `uv python install` or a package download.
- **Cause:** NAT gateway or private route table is missing.
- **Check:** VPC console → route table for the app subnets must have `0.0.0.0/0` → NAT gateway. The NAT gateway must be in a public subnet and have an Elastic IP.
- **Fix:** re-apply Terraform. NAT creation is verified as allowed (`specs/answered-questions.md`, Q-004).

### T4. API cannot reach RDS

- **Symptom:** logs show `Can't connect to MySQL server`.
- **Check:** `db-sg` must allow TCP 3306 from `app-sg`. The DB instance must be in the `docuprocess-sandbox-db` subnet group.
- **Fix:** re-apply Terraform. Do not open the database to `0.0.0.0/0`.

### T5. Migration fails at boot

- **Symptom:** `journalctl` shows a migration error.
- **Cause:** another instance holds the migration lock, or a migration file is broken.
- **Fix:** migrations take a MySQL lock, so the second instance waits. If the lock is stuck, check `SHOW PROCESSLIST` through a session on an instance. Do not edit `schema_migrations` by hand.

### T6. OCR fails on a missing system package

- **Symptom:** jobs fail with `OCR_FAILED` and reason `PROVIDER_PERMANENT`, and the bootstrap log shows `tesseract: command not found`.
- **Cause:** the package install step did not run or used a wrong package name (`ADR-012`).
- **Fix:** run `tesseract --version` on the instance, fix the package name in userData, and redeploy.

### T7. SNS email does not arrive

- **Cause:** the subscription was never confirmed (see step 9).
- **Fix:** confirm the subscription from the email. Confirmation links expire, so request a new one by deleting and recreating the subscription in Terraform, or re-run `make deploy`.

### T8. CloudFront serves old files

- **Fix:** run `make deploy-frontend` again, or create an invalidation for `/*` manually:
  ```sh
  aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
  ```

### T9. Terraform fails with AccessDenied on a service

- **Check:** the service must appear in the sandbox service list (`specs/02-aws-sandbox-constraints.md` section 0). If it does, the sandbox may have blocked a specific action. Note the exact action from the error message.
- **Fix:** do not add IAM permissions. Record the blocker in `specs/open-questions.md`, and use the documented fallback if one exists.

### T10. CloudTrail cannot be created

- **Cause:** `cloudtrail:CreateTrail` is denied for the lab role (`specs/answered-questions.md`, Q-003).
- **Fix:** set `enable_cloudtrail = false` and record the blocker in `risks-and-exceptions.md`.

## Known limitations

These are accepted for the sandbox and listed in `risks-and-exceptions.md` (once written):
- Single NAT gateway and Single-AZ RDS.
- HTTP between CloudFront and the ALB.
- RDS not encrypted at rest.
- Terraform state is local. Keep `infra/terraform/terraform.tfstate` safe; losing it means Terraform no longer knows the resources it created.

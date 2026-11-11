# Deployment guide

The local application is implemented. This guide describes the AWS deployment procedure; it is not evidence that the current sandbox is deployed. Complete the acceptance checklist in `specs/10-testing-and-acceptance.md` and record actual outcomes.

## 1. Prepare Ubuntu/WSL

Use Python 3.12, uv, make, Terraform 1.6+, Git, AWS CLI and Tesseract with Spanish/English data. Run all project commands from the repository root in Ubuntu 24.04.

```sh
sudo apt-get update
sudo apt-get install -y make python3-venv tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
make setup
make lint
make typecheck
make test
make test-ocr
make tf-validate
make package VERSION=1.0.0
```

Expected: every command exits 0. Terraform initialization downloads providers but does not create AWS resources. The release archive and OpenAPI document are generated locally.

`make demo` starts the portal at http://127.0.0.1:8000 with temporary SQLite and mocked S3/DynamoDB/SNS. It uses real Tesseract. This is local functional evidence only.

## 2. Verify the sandbox and recover state

Start the AWS Academy lab. Update the temporary credentials in the WSL user's `~/.aws/credentials`, using the intended profile; never place credentials in the repository or paste them into evidence. Set the CLI region to `us-east-1`.

```sh
bash scripts/aws_sandbox_check.sh
aws iam list-instance-profiles --query "InstanceProfiles[?contains(InstanceProfileName, 'SsmRoleInstanceProfile')].InstanceProfileName" --output text
terraform -chdir=infra/terraform state list
```

If the session is expired, stop AWS checks until credentials are renewed. The profile changes between sessions. If no local state is available, inspect the existing EC2/ASG, RDS, DynamoDB, S3, CloudFront and CloudFormation resources using the read-only checks and console. Recover the state backup or plan imports before creating anything with matching names. Never delete or recreate resources merely because a state file is missing.

Terraform state contains the generated database password. Keep it private and backed up outside Git.

## 3. Configure and review the plan

```sh
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Set `instance_profile_name` to the discovered value and `alert_email` to the recipient for processing/operational notifications. Leave `release_version = ""` until publication. Keep `asg_health_check_type = "ELB"`; infrastructure-only startup explicitly uses EC2 health checks until a release is configured.

```sh
make tf-plan
```

Review the plan before approval: no IAM creation, Lambda, custom DNS/certificates, public RDS or SSH; two private application instances, Single-AZ RDS, and the documented sandbox instance/storage limits. A saved plan is sensitive because it may contain state values.

## 4. Bootstrap buckets and publish the release

The buckets are owned by the `buckets` module through CloudFormation (ADR-035). The artifact must exist before application instances start.

After explicit approval for bucket creation:

```sh
make bootstrap-artifacts
```

After explicit approval for uploading the prepared artifact:

```sh
make publish VERSION=1.0.0
```

Expected: the artifact is at `releases/1.0.0/docuprocess-1.0.0.tar.gz` in the artifacts bucket. A bucket-only targeted apply is initial preparation, not a complete infrastructure deployment.

## 5. Deploy the application stack

After reviewing and approving the full release plan:

```sh
make deploy VERSION=1.0.0
```

The target creates a saved plan with the published version and ELB health checks, then applies it. Set the same version in the private tfvars file afterwards so future plans do not revert to infrastructure-only startup. New releases must use new version identifiers. The lab denies `autoscaling:StartInstanceRefresh`, so a launch-template change does not replace running instances. Replace them one at a time, waiting for each replacement to be healthy (ADR-039):

```sh
aws autoscaling terminate-instance-in-auto-scaling-group --instance-id <instance-id> --no-should-decrement-desired-capacity
```

At boot each instance downloads the release, installs locked runtime dependencies and the three application packages, verifies MySQL TLS against the RDS CA, and runs forward-only migrations. MySQL `GET_LOCK` serializes migration runners. Systemd then starts the API and worker. RDS remains private.

Find the target-group ARN in the ALB console, then:

```sh
aws elbv2 describe-target-health --target-group-arn <target-group-arn>
```

Expected: two targets become healthy on `/api/v1/health`. Terraform completion alone does not establish application health. Allow time for RDS provisioning, package installation and health checks.

## 6. Confirm SNS and deploy the frontend

Confirm both SNS subscription emails manually. A successful SNS publish does not prove that email delivery is confirmed.

After explicit approval for uploading frontend assets and creating a CloudFront invalidation:

```sh
make deploy-frontend
terraform -chdir=infra/terraform output -raw cloudfront_domain_name
```

Open the resulting HTTPS domain. Static pages and `/api/v1` share that origin; CloudFront forwards API requests to the ALB and disables API caching. Security headers are delivered by CloudFront.

## 7. Run live acceptance

```sh
SMOKE_BASE_URL=https://<cloudfront-domain> make smoke
```

Expected: health/register/login/upload/poll/logout return the expected HTTP statuses and the script exits 0. It prints no tokens or response bodies. It creates a synthetic account and document in the deployed system.

Repeat through the browser; verify the S3 object, terminal document/job in DynamoDB, and SNS email. The synthetic receipt total should be COP 119000.00. Verify rejection of oversized, encrypted, multi-page and renamed invalid files, owner isolation and logout.

Complete TST-E2E-01..15 in the testing specification: two healthy targets, SSM without SSH, effective S3/DynamoDB/SNS permissions from an instance, alarm delivery, CloudTrail or its documented restriction, controlled scale-out and a second plan with no unintended changes. After an approved instance refresh/replacement, confirm previously registered users and documents remain available. These live checks remain pending until observed.

## 8. Optional first administrator

Register the intended account normally. In an authorized SSM shell on an application instance, promote that existing account through the migration runner:

```sh
sudo bash
set -a
. /etc/docuprocess/app.env
set +a
export DOCUPROCESS_BOOTSTRAP_ADMIN_EMAIL='<registered-email>'
/opt/docuprocess/current/.venv/bin/python -m api.migrate
unset DOCUPROCESS_BOOTSTRAP_ADMIN_EMAIL
exit
```

This is an explicit database write requiring operator authorization. It does not create a default password or an unauthenticated bootstrap endpoint. Later role changes use the authenticated admin API.

## Troubleshooting

| Symptom | Check and correction |
|---|---|
| Targets unhealthy | SSM: `sudo tail -n 100 /var/log/docuprocess-bootstrap.log`, `sudo journalctl -u docuprocess-api -n 100 --no-pager`, `curl -i localhost:8000/api/v1/health`. Health requires RDS and DynamoDB. |
| Artifact download denied or missing | Confirm the published version/key and bucket policy for the existing instance role. Publish the same version before booting instances. |
| Package downloads stall | Check private route tables, NAT gateway and its public route/EIP. Do not assign public instance IPs to work around routing. |
| Launch template authorization failure | Confirm the explicit gp2 root mapping and permitted instance type (ADR-034). |
| RDS unreachable/TLS error | Check app-to-DB security groups, private subnet group and the RDS CA download. Preserve certificate and hostname verification. |
| Migration fails | Inspect the bootstrap log and MySQL advisory lock owner. Both instances must use the same lock and packaged migrations. Do not edit migration history manually. |
| OCR fails | Check `tesseract --version` and `tesseract --list-langs` on the instance. The instances run Ubuntu 24.04 and install `tesseract-ocr`, `tesseract-ocr-spa` and `tesseract-ocr-eng` with apt (ADR-038). |
| Job stuck or retried | Inspect its status/available_at/attempts in the jobs table and `sudo journalctl -u docuprocess-worker -n 100 --no-pager`. Expired owners cannot commit results. |
| SNS email absent | Check subscription confirmation and notification_status. After three failed publication attempts the job remains terminal; it is not processed again. Publication and database commit are not one transaction (ADR-036). |
| Stale frontend | Re-run the approved frontend deployment/invalidation. Confirm the distribution has finished deploying. |
| AWS AccessDenied | Record the action, service and caller context. Lab-role success does not prove instance-role access. Do not create IAM policies to bypass sandbox restrictions. |
| CloudTrail denied | Record the exact failure and accepted exception before changing enable_cloudtrail. Refer to previous evidence in specs/answered-questions.md. |
| UI cannot retain sessionStorage | The page uses per-tab memory navigation. Reloading requires sign-in again. Tokens never use localStorage. |

## Teardown

Only after approval for destroying the complete stack:

```sh
make destroy
```

The target displays the destroy plan, empties the output-named buckets including versions/delete markers, then runs Terraform destroy with its interactive approval. CloudFormation cannot delete nonempty buckets. Stop application writes before teardown and verify RDS, EC2, NAT, buckets and CloudFront are removed. No final RDS snapshot is kept.

Accepted limitations and verification boundaries are in [risks-and-exceptions.md](risks-and-exceptions.md).

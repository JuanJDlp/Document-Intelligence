# 03 — Infrastructure (Terraform)

Constraints in `02-aws-sandbox-constraints.md` apply to every resource here. If a requirement below conflicts with it, the constraint wins and a `Q-` item is logged.

## 1. Tooling

- **INF-TOOL-01** (active) Terraform `>= 1.6, < 2.0`. AWS provider `hashicorp/aws ~> 5.0`. The lock file `.terraform.lock.hcl` MUST be committed.
- **INF-TOOL-02** (active) Single root module at `infra/terraform/` that composes child modules under `infra/terraform/modules/`.
- **INF-TOOL-03** (active) The provider block sets `default_tags` (see section 2) and `region` from a variable. No credentials are written in code; the operator uses the Academy CLI credentials.
- **INF-TOOL-04** (active) A `terraform.tfvars.example` file documents every variable. The real `terraform.tfvars` is git-ignored.

## 2. Naming and tags

- **INF-NAME-01** (active) Prefix: `docuprocess`. Environment: `sandbox`. Resource names follow `docuprocess-sandbox-<purpose>`, for example `docuprocess-sandbox-alb`.
- **INF-NAME-02** (active) S3 bucket names are globally unique. They follow `docuprocess-sandbox-<purpose>-<account_id>` where `account_id` comes from `data "aws_caller_identity"` (STS, not IAM).
- **INF-TAG-01** (active) Every taggable resource receives via `default_tags`:
  - `Project = "DocuProcessCloud"`
  - `Environment = "sandbox"`
  - `ManagedBy = "terraform"`
  - `Course = "infraestructura-iii"`

## 3. Network module (`modules/network`)

- **INF-NET-01** (active) One VPC, CIDR `10.0.0.0/16`, DNS support and DNS hostnames enabled.
- **INF-NET-02** (active) Subnets (one per AZ, two AZs = first two AZs in the region returned by `data "aws_availability_zones"` with state `available`):

  | Subnet | CIDR | AZ index | Public IP on launch |
  |---|---|---|---|
  | public-a | `10.0.101.0/24` | 0 | yes |
  | public-b | `10.0.102.0/24` | 1 | yes |
  | app-a (private) | `10.0.1.0/24` | 0 | no |
  | app-b (private) | `10.0.2.0/24` | 1 | no |
  | db-a (private) | `10.0.11.0/24` | 0 | no |
  | db-b (private) | `10.0.12.0/24` | 1 | no |

- **INF-NET-03** (active) One Internet Gateway attached to the VPC.
- **INF-NET-04** (active) One NAT gateway with one Elastic IP, placed in `public-a`. It is a single point of failure by design (`ADR-005`).
- **INF-NET-05** (active) Route tables: public (default route to IGW); app (default route to NAT); db (no default route).
- **INF-NET-06** (active) Gateway VPC endpoints for `com.amazonaws.us-east-1.s3` and `com.amazonaws.us-east-1.dynamodb`, associated with the app route table. They are free.
- **INF-NET-07** (active) Subnet groups: `docuprocess-sandbox-db` containing `db-a` and `db-b` (required even for Single-AZ RDS).

## 4. Security groups (`modules/network` or `modules/security`)

- **INF-SG-01** (active) `alb-sg`: ingress TCP 80 from `0.0.0.0/0`; egress TCP 8000 to `app-sg`.
- **INF-SG-02** (active) `app-sg`: ingress TCP 8000 only from `alb-sg`; egress all (needed for NAT, SNS, and package installs).
- **INF-SG-03** (active) `db-sg`: ingress TCP 3306 only from `app-sg`; no egress rules.
- **INF-SG-04** (active) No security group allows port 22. No security group allows `0.0.0.0/0` to anything except the ALB port 80.

## 5. Storage and content delivery

### 5.1 Frontend (`modules/frontend`)
- **INF-CDN-01** (active) S3 bucket `frontend-assets` with all public access blocked.
- **INF-CDN-02** (active) CloudFront distribution with two origins:
  1. the `frontend-assets` S3 bucket, through Origin Access Control (default behavior);
  2. the ALB, as a custom origin with `origin_protocol_policy = "http-only"` on port 80 (behavior path pattern `/api/*`).
  Default root object `index.html`. Viewer protocol policy `redirect-to-https` on both behaviors. Price class `PriceClass_100`. Default certificate (no custom domain, `CON-DNS-02`).
- **INF-CDN-05** (active) The `/api/*` behavior uses the managed cache policy `CachingDisabled` and the managed origin request policy `AllViewerExceptHostHeader`, so that `Authorization`, `Content-Type`, the query string, and all HTTP methods (`GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE`) reach the API. Its origin is the ALB, not S3.
- **INF-CDN-06** (active) Rationale (`ADR-030`): the frontend is served over HTTPS by CloudFront, and the ALB has no certificate (`CON-DNS-02`). Browsers block HTTP API calls from an HTTPS page (mixed content). Routing `/api/*` through CloudFront makes the frontend and the API **same-origin over HTTPS**.
- **INF-CDN-03** (active) Bucket policy allows `s3:GetObject` only to the CloudFront service principal with `AWS:SourceArn` equal to the distribution ARN.
- **INF-CDN-04** (active) Frontend assets are uploaded by `scripts/deploy_frontend.sh` (`ADR-007`). Terraform does not upload files.

### 5.2 Uploads (`modules/storage`)
- **INF-S3-01** (active) Bucket `uploads` (private, public access blocked, SSE-S3 default encryption, versioning disabled). Created by CloudFormation (`ADR-035`); its policy is managed by Terraform (`INF-RPOL-02`).
- **INF-S3-02** (active) Object keys: `uploads/{user_id}/{document_id}/{safe_filename}`. Filenames are sanitized (see `API-DOC-05`).

### 5.3 Artifacts (`modules/storage`)
- **INF-S3-03** (active) Bucket `artifacts` (private, SSE-S3). Keys: `releases/{version}/docuprocess-{version}.tar.gz`. Written by `scripts/publish_release.sh`, read by EC2 userData.

### 5.4 Audit logs (`modules/audit`)
- **INF-AUD-01** (active) Bucket `audit-logs` with a bucket policy that allows `cloudtrail.amazonaws.com` to write (`s3:PutObject`, `s3:GetBucketAcl`) and public access blocked. Lifecycle expiry after 30 days.

## 6. DynamoDB (`modules/dynamodb`)

- **INF-DDB-01** (active) Billing mode `PAY_PER_REQUEST` for both tables.
- **INF-DDB-02** (active) Table `documents`, key and indexes as specified in `07-data-model.md` section 2.
- **INF-DDB-03** (active) Table `jobs`, key and indexes as specified in `07-data-model.md` section 3.
- **INF-DDB-04** (active) Point-in-time recovery disabled (sandbox cost). Deletion protection disabled so the sandbox can be destroyed.

## 7. Relational database (`modules/database`)

- **INF-RDS-01** (active) Engine `mysql`, version `8.0` (major version pinned in a variable). `multi_az = false` (`CON-RDS-02`).
- **INF-RDS-02** (active) Instance class variable `db_instance_class`, default `db.t3.micro`. Allocated storage variable, default `20`, storage type `gp2`.
- **INF-RDS-03** (active) `publicly_accessible = false`. Placed in subnet group `docuprocess-sandbox-db` with `db-sg`.
- **INF-RDS-04** (active) Database name `docuprocess`, master username `docuprocess_admin`. The master password is generated by `random_password` (length 24, no special characters that break connection strings: use `special = false` plus a number/letter mix).
- **INF-RDS-05** (active) `skip_final_snapshot = true`, `deletion_protection = false`, `backup_retention_period = 1` (sandbox limits; documented in `docs/`).
- **INF-RDS-06** (active) The password is stored in SSM Parameter Store as `SecureString` at `/docuprocess/sandbox/db/password` (`SEC-SEC-02`). Verified 2026-11-03: the instance role may call `ssm:GetParameter` (`ADR-033`).

## 8. Compute (`modules/compute`)

- **INF-EC2-01** (active) AMI: `data "aws_ami"` owner `amazon`, name `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*`, most recent. The launch template takes the root device name from the AMI. (`CON-EC2-04`, `ADR-038`)
- **INF-EC2-02** (active) Launch template:
  - instance type variable, default `t3.micro`;
  - `iam_instance_profile { name = var.instance_profile_name }` with no default; its value is discovered per session (`CON-IAM-03`);
  - no `key_name` (`CON-EC2-05`);
  - IMDSv2 required (`http_tokens = "required"`);
  - root EBS mapped explicitly as `gp2`, 20 GB, encrypted. The AMI default `gp3` is denied for the lab role (`ADR-034`);
  - security group `app-sg`;
  - no public IP;
  - `user_data` base64-encoded from `templates/userdata.sh.tftpl`.
- **INF-EC2-03** (active) The userData template is described in section 12.
- **INF-EC2-04** (active) The Auto Scaling group always uses the latest launch template version and has no `instance_refresh` block (the lab denies `autoscaling:StartInstanceRefresh`). A new release or AMI is rolled out by replacing instances one at a time (`ADR-039`).

### 8.1 Auto Scaling Group
- **INF-ASG-01** (active) `min_size = 2`, `desired_capacity = 2`, `max_size = 4`. (`CON-EC2-02`)
- **INF-ASG-02** (active) Subnets: `app-a`, `app-b`. Target group attached (see ALB).
- **INF-ASG-03** (active) `health_check_type = "ELB"`, `health_check_grace_period = 300`.
- **INF-ASG-04** (active) Target tracking scaling policy `cpu-target-60`: `ASGAverageCPUUtilization` target `60`. Scale-in and scale-out enabled. Instance warmup 180 s.
- **INF-ASG-05** (active) Tags propagated to instances: `Name = docuprocess-sandbox-app`, plus the default tags.

## 9. Load balancer (`modules/alb`)

- **INF-ALB-01** (active) Internet-facing Application Load Balancer in `public-a` and `public-b`, security group `alb-sg`. Idle timeout 60 s.
- **INF-ALB-02** (active) Listener HTTP 80 forwards to target group `docuprocess-sandbox-api`.
- **INF-ALB-03** (active) Target group: protocol HTTP, port 8000, target type `instance`, health check path `/api/v1/health`, matcher `200`, interval 15 s, healthy threshold 2, unhealthy threshold 3, deregistration delay 30 s.
- **INF-ALB-04** (active) No HTTPS listener (no custom domain or ACM certificate, `CON-DNS-02`). Known limitation documented as `SEC-NET-03`.

## 10. Messaging and monitoring (`modules/monitoring`)

- **INF-SNS-01** (active) Topic `docuprocess-sandbox-processing-events`. Subscription protocol `email` to variable `alert_email`. The subscription requires manual confirmation by the recipient; the runbook must say so.
- **INF-SNS-02** (active) Topic `docuprocess-sandbox-ops-alarms` (separate topic for alarms) subscribed to the same `alert_email`.
- **INF-MON-01** (active) CloudWatch alarms, each with `alarm_actions` pointing to `ops-alarms`:

  | Alarm | Metric | Condition |
  |---|---|---|
  | `asg-cpu-high` | EC2 `CPUUtilization` (ASG dimension), Average, 300 s | > 80 for 2 periods |
  | `asg-in-service-low` | `GroupInServiceInstances` (ASG) | < 2 for 2 periods |
  | `alb-unhealthy-hosts` | ALB `UnHealthyHostCount` (target group dimension), Maximum, 60 s | ≥ 1 for 3 periods |
  | `alb-5xx-high` | ALB `HTTPCode_Target_5XX_Count`, Sum, 300 s | > 10 for 1 period |
  | `rds-cpu-high` | RDS `CPUUtilization`, Average, 300 s | > 80 for 2 periods |
  | `rds-free-storage-low` | RDS `FreeStorageSpace`, Minimum, 300 s | < 2 GB for 1 period |
  | `rds-connections-high` | RDS `DatabaseConnections`, Maximum, 300 s | > 40 for 2 periods |

- **INF-MON-02** (active) A CloudWatch dashboard `docuprocess-sandbox` shows: ASG CPU, ASG in-service count, ALB request count, ALB 5xx, RDS CPU, RDS connections, and the `jobs` table consumed capacity.
- **INF-MON-03** (active) Alarm names and thresholds are variables with the defaults above.

## 11. Audit (`modules/audit`)

- **INF-AUD-02** (active) CloudTrail trail `docuprocess-sandbox-trail` writes to the `audit-logs` bucket. `include_global_service_events = true`, `is_multi_region_trail = false` (cost and sandbox scope), `enable_log_file_validation = true`.
- **INF-AUD-03** (active) `cloudtrail:CreateTrail` is denied for the lab role (`specs/answered-questions.md`, Q-003). The module is therefore disabled by default through variable `enable_cloudtrail = false`, and the deliverable doc records the blocker. Set `true` only if the trail can be created.

## 12. Bootstrap and userData (`templates/userdata.sh.tftpl`)

userData runs once per instance at first boot. It MUST be idempotent (safe to re-run).

- **INF-UD-01** (active) Install system packages needed for the runtime with `apt-get` (`curl`, `unzip`, `tar`, `gzip`, and `tesseract-ocr`, `tesseract-ocr-spa`, `tesseract-ocr-eng` when `ocr_provider = "tesseract"`), then AWS CLI v2 from the official AWS installer if `aws` is not present (`ADR-038`).
- **INF-UD-02** (active) Install `uv` and provision Python 3.12 with `uv python install 3.12`. If the default image lacks network access, the instance fails loudly (exit code non-zero) and the ASG replaces it.
- **INF-UD-03** (active) Download `s3://<artifacts>/releases/<release_version>/docuprocess-<release_version>.tar.gz` to `/opt/docuprocess/releases/<release_version>/` and link `/opt/docuprocess/current`.
- **INF-UD-04** (active) Create a venv under `/opt/docuprocess/current/.venv` and install the packages `app/receipt_engine`, `app/worker`, `app/api` from the release (pinned wheels, no network index needed beyond the NAT).
- **INF-UD-05** (active) Write `/etc/docuprocess/app.env` with mode `0600`, owner `root`, containing non-secret values rendered by Terraform and the DB password (see `INF-RDS-06`).
- **INF-UD-06** (active) Run database migrations with `python -m api.migrate`. The migration command MUST take a MySQL advisory lock (`GET_LOCK`) so that concurrent instances do not race.
- **INF-UD-07** (active) Install and enable systemd units `docuprocess-api.service` (Uvicorn on `0.0.0.0:8000`) and `docuprocess-worker.service`. Both `Restart=always`, `RestartSec=5`, and run as user `docuprocess`.
- **INF-UD-08** (active) userData writes its logs to `/var/log/docuprocess-bootstrap.log` and exits non-zero on failure.

## 13. Variables (minimum set)

| Variable | Default | Notes |
|---|---|---|
| `region` | `us-east-1` | Diagram region |
| `project` | `docuprocess` | Name prefix |
| `environment` | `sandbox` | Only `sandbox` is valid |
| `instance_profile_name` | none (required) | Sandbox SSM profile, discovered per session, never created |
| `instance_type` | `t3.micro` | `CON-EC2-01` |
| `asg_min_size` / `asg_max_size` | `2` / `4` | `CON-EC2-02` |
| `vpc_cidr` | `10.0.0.0/16` | |
| `db_instance_class` | `db.t3.micro` | `CON-RDS-01` |
| `db_allocated_storage` | `20` | ≤ 100 GB, `CON-RDS-03` |
| `db_engine_version` | `8.0` | |
| `alert_email` | none (required) | SNS email recipient |
| `release_version` | none (required) | Artifact version to deploy |
| `ocr_provider` | `tesseract` | Only `tesseract` in v1 (`ADR-012`) |
| `max_upload_bytes` | `5242880` | Must match `ENG-VAL-02` |
| `enable_cloudtrail` | `true` | `INF-AUD-03` |

## 14. Outputs (minimum set)

`alb_dns_name`, `cloudfront_domain_name`, `frontend_bucket_name`, `artifacts_bucket_name`, `uploads_bucket_name`, `documents_table_name`, `jobs_table_name`, `db_endpoint` (non-sensitive hostname), `db_name`, `processing_events_topic_arn`, `asg_name`, `release_version`.

Outputs MUST NOT include the DB password.

## 15. Deployment order (required, enforced by Makefile)

1. `make tf-validate`, then `make tf-plan` (operator reviews).
2. Bootstrap the artifacts bucket: `terraform apply -target=module.buckets` (creates the bucket that the release is uploaded to).
3. `make package` and `scripts/publish_release.sh <version>` (uploads to `artifacts` bucket).
4. Full `terraform apply -var release_version=<version>`.
5. Wait for ALB health check `200` on `/api/v1/health`.
6. `scripts/deploy_frontend.sh` (uploads `app/frontend` to the frontend bucket and writes `config.js` with the API base URL), then CloudFront invalidation.
7. Confirm the SNS subscription email.
8. Run `make smoke`.

## 16. State and teardown

- **INF-STATE-01** (active) Terraform state is local (`infra/terraform/terraform.tfstate`), git-ignored, and never copied into the repository. A remote backend is out of scope because the sandbox would need an extra bucket and lock table; the operator keeps the state file for the duration of the course.
- **INF-STATE-02** (active) The four S3 buckets are created by a CloudFormation stack (`ADR-035`). `make tf-destroy` empties them with `scripts/empty_buckets.sh` before destroying the stack. Sandbox data is disposable.
- **INF-STATE-03** (active) `make destroy` prints the destroy plan first and requires explicit approval (`TST-MK-13`).

## 17. Resource policies for the instance role

The instance role has no identity-based permission for S3, DynamoDB, or SNS. Access is granted by policies on each resource that name the role ARN (`ADR-033`).

- **INF-RPOL-01** (active) The role ARN is built as `arn:aws:iam::<account_id>:role/<instance_profile_role_name>` from `data "aws_caller_identity"` (STS). No IAM read is performed (`CON-IAM-02`).
- **INF-RPOL-02** (active) Bucket `uploads` grants the role `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, and `s3:ListBucket`. Bucket `artifacts` grants `s3:GetObject` and `s3:ListBucket`.
- **INF-RPOL-03** (active) Tables `documents` and `jobs` grant the role `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Query`, and `DescribeTable`, on the table and its indexes.
- **INF-RPOL-04** (active) Topic `processing-events` grants the role `sns:Publish`.
- **INF-RPOL-05** (active) A policy naming the account root is NOT used. It delegates only to identities that already have permissions, so it does not grant access here.

## 18. Acceptance for this spec

- **INF-ACC-01** (active) `terraform validate` passes with no warnings on a clean clone.
- **INF-ACC-02** (active) `terraform plan` from an empty sandbox produces no resource type listed in `02` section 3.
- **INF-ACC-03** (active) A full apply from an empty sandbox followed by `make smoke` succeeds (`TST-E2E-*`).
- **INF-ACC-04** (active) A second apply on the unchanged configuration shows no changes.

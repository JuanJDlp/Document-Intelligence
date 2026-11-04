# 02 — AWS Academy Sandbox constraints

Source: course brief, section 4 (`guia_proyecto_final.pdf`), plus facts that were not verified yet (listed in section 4 of this file and in `open-questions.md`).

Every agent MUST read this file before writing any Terraform, any AWS SDK call, or any userData script.

## 0. Official sandbox allowance (AWS Academy lab overview)

The lab overview is the authoritative list of what the sandbox tolerates. It is provided by the user and applies on top of the course brief. Anything not listed here is not allowed.

| Service | Allowed scope (lab overview) | Our use |
|---|---|---|
| EC2 | `t2`/`t3` from `t.nano` to `t.medium`; EBS `gp2` up to 35 GB; On-Demand only; Amazon-provided AMIs (Linux and Windows) | `t3.micro`, 20 GB `gp2`, Amazon Linux 2023 (`CON-EC2-*`) |
| RDS | `db.t2`/`db.t3` from `db.t.micro` to `db.t.medium`; Single AZ only ("Do not create a standby instance"); storage `gp2` up to 100 GB; engines Aurora, MySQL, PostgreSQL, MariaDB; On-Demand | `db.t3.micro`, MySQL 8.0, Single-AZ, 20 GB (`CON-RDS-*`) |
| IAM | **Read access** only; List access | No IAM writes (`CON-IAM-01`). Terraform makes no IAM calls (`CON-IAM-02`). |
| EC2 Auto Scaling | Allowed | ASG with target tracking (`INF-ASG-*`) |
| CloudFormation | Allowed | Not used; Terraform chosen (`ADR-001`) |
| CloudWatch | Allowed | Alarms and dashboard (`INF-MON-*`) |
| Systems Manager Session Manager | Allowed; requires the SSM instance role attached to the instance | Operator access, no SSH (`CON-EC2-05`). Profile name discovered per session (`CON-IAM-03`). |
| SNS | Allowed | Processing and ops topics (`INF-SNS-*`) |
| S3 | Allowed | Frontend, uploads, artifacts, audit logs (`INF-S3-*`, `INF-CDN-*`, `INF-AUD-*`) |
| Amazon Glacier | Allowed | Not used |
| Elastic Load Balancing | Allowed | ALB (`INF-ALB-*`) |
| Route53 | Allowed | Not used: the course brief forbids custom domains (`CON-DNS-01`) |
| Lambda | Allowed by the lab overview | **Not used.** The instance role trusts only EC2, and roles cannot be created (`ADR-023`). |
| CloudFront | Allowed | Frontend and `/api/*` routing (`INF-CDN-*`) |
| DynamoDB | Allowed | `documents` and `jobs` tables (`DAT-DDB-*`) |
| CloudTrail | Allowed | Audit trail (`INF-AUD-*`) |
| KMS | List access only | Not used. Encryption at rest uses SSE-S3 and the RDS/EBS defaults. No KMS keys are created. |
| Tagging | Allowed | `default_tags` (`INF-TAG-01`) |

### 0.1 Reconciliation with the course brief

Where the two sources differ, the more restrictive rule applies until the difference is verified:

- **Lambda** (was Q-007): verified 2026-11-03. The instance role trusts only `ec2.amazonaws.com`, and creating roles is denied, so Lambda cannot run under the course roles. Not used (`ADR-023`).
- **Route53**: lab overview allows it; the course brief forbids custom domains. We follow the brief: default DNS names only (`CON-DNS-01`).
- **SSM instance role name**: the sandbox has no profile named `AmazonSSMRoleForInstancesQuickSetup`. It provides one whose name contains `SsmRoleInstanceProfile`, with a prefix and suffix that change per lab. The `aws-sandbox` skill discovers it each session and writes it to `terraform.tfvars`. The role `AmazonSSMRoleForInstancesQuickSetup` does exist inside that profile, so the course name is valid for the role, not the profile.
- **IAM** (was Q-009): verified 2026-11-03. `iam:GetRole` works for the instance role, so the brief's denial does not hold here. Terraform still makes no IAM calls (`CON-IAM-02`), by design.
- **EC2 launch** (was Q-013): verified 2026-11-03. The lab role denies `ec2:RunInstances` for volumes of type `gp3`. The default AMI root volume is `gp3`, so the launch template must map the root volume explicitly as `gp2` (`ADR-034`). Auto Scaling then launches and reaches `InService`. Evidence in `specs/answered-questions.md`.
- **OCR** (was Q-002): verified 2026-11-03. The instance role has no Textract permission, so OCR runs locally (`ADR-012`).
- **Data access of the instance role** (was Q-001): verified 2026-11-03. The role has `ssm:*` on parameters and no identity-based permission for S3, DynamoDB, SNS, or SQS. Access works through resource policies that name the role ARN (`ADR-033`).
- **Instance count**: the course brief says 9 concurrent EC2 instances (`CON-EC2-02`); the lab overview does not state it. Kept as is (`Q-006`).
- **KMS**: list access only, so no customer-managed keys (`CON-KMS-01`).

- **CON-KMS-01** (active) No `aws_kms_key` resources and no KMS `Decrypt`/`Encrypt` calls with customer-managed keys. Use SSE-S3 and default service encryption.
- **CON-SVC-01** (active) Any service not in section 0 MUST NOT be used. Adding one requires a `D-` decision and an update to this table first.

## 1. Validated restrictions (from the course brief)

### 1.1 IAM

- **CON-IAM-01** (active) The Academy account MUST NOT create IAM roles, policies, or instance profiles. Terraform MUST NOT contain `aws_iam_role`, `aws_iam_policy`, `aws_iam_role_policy`, `aws_iam_instance_profile`, or `aws_iam_role_policy_attachment` resources.
- **CON-IAM-02** (active) Terraform MUST NOT use data sources that read IAM roles or profiles (`data "aws_iam_role"`, `data "aws_iam_policy_document"` is allowed because it is local).
- **CON-IAM-03** (active) Compute MUST use only the pre-existing SSM instance profile of the sandbox, referenced by name. Its name contains `SsmRoleInstanceProfile` and changes per lab. It is discovered each session and passed as the Terraform variable `instance_profile_name`, which has no default. Terraform MUST NOT look it up through IAM APIs; it is passed by name to `aws_launch_template`.
- **CON-IAM-04** (active) No resource may require a service role that we create. This rules out: Textract async jobs (they need a role to publish to SNS), CloudFormation service roles, ASG lifecycle hooks that need a role, and Lambda.

### 1.2 Compute

- **CON-EC2-01** (active) Instance types MUST be `t2.*` or `t3.*` between `nano` and `medium`. The default is `t3.micro`.
- **CON-EC2-02** (active) Maximum 9 concurrent EC2 instances in the account. The ASG `max_size` MUST be ≤ 4 (see `INF-ASG-*`).
- **CON-EC2-03** (active) EBS volumes MUST be `gp2` and ≤ 35 GB.
- **CON-EC2-04** (active) AMIs MUST be provided by Amazon. Terraform resolves the AMI through `data "aws_ami"` filtered by owner `amazon`.
- **CON-EC2-05** (active) Port 22 (SSH) MUST NOT be open. Operator access is through AWS Systems Manager Session Manager. No bastion host.
- **CON-EC2-06** (active) Instances use the sandbox SSM instance profile (`CON-IAM-03`) for Systems Manager. The userData MUST NOT rely on any other instance-level permission until it is verified (see `ADR-033`).

### 1.3 Lambda

- **CON-LAM-01** (active) Lambda MUST NOT be used. No `aws_lambda_*` resources. The Academy roles have no trust policy for `lambda.amazonaws.com`.

### 1.4 RDS

- **CON-RDS-01** (active) Only `db.t2.*` or `db.t3.*` classes between `micro` and `medium`. The default is `db.t3.micro`.
- **CON-RDS-02** (active) Deployments MUST be Single-AZ. `multi_az = false` is mandatory. The "do not create a standby" option applies.
- **CON-RDS-03** (active) Storage type `gp2`, size ≤ 100 GB. The default is 20 GB.
- **CON-RDS-04** (active) Engine MUST be one of: `aurora-mysql`, `mysql`, `postgres`, `mariadb`. We use `mysql` 8.0 (see `ADR-003`).
- **CON-RDS-05** (active) The DB instance MUST NOT be publicly accessible (`publicly_accessible = false`).

### 1.5 Networking and DNS

- **CON-DNS-01** (active) Route53 custom domain registration is not allowed. Use the default DNS names: the ALB DNS name and the CloudFront domain name.
- **CON-DNS-02** (active) No ACM certificates for custom domains. HTTPS is provided by CloudFront's default certificate on the frontend. The ALB serves HTTP on port 80 for API traffic (documented as a known limitation in `09-security-observability.md`, `SEC-NET-03`).

### 1.6 Infrastructure as Code

- **CON-IAC-01** (active) Deployments MUST be automated with **Terraform** (chosen; see `ADR-001`). CloudFormation is not used.
- **CON-IAC-02** (active) Terraform MUST NOT perform IAM reads or writes (see section 1.1).

## 2. Services we plan to use (allowed by the brief)

VPC (including IGW, NAT gateway, route tables, endpoints), EC2 (Launch Template, ASG, scaling policies), ALB, S3, CloudFront, RDS (MySQL), DynamoDB, SNS, CloudWatch (alarms, dashboard), CloudTrail, Systems Manager Session Manager, SSM Parameter Store (verified, `ADR-033`).

## 3. Explicitly not used

- Lambda, API Gateway, ECS/EKS, Route53, ACM for custom domains, Textract async (`StartDocumentAnalysis`, `StartExpenseAnalysis`), SQS/SNS-based job queues, IAM (any write, any read), Bastion hosts, SSH key pairs.

## 4. Unverified sandbox facts

These are **not** yet confirmed. Each has a planned fallback. They are tracked in `open-questions.md`. Facts already verified are in section 0.1, not here.

| ID | Fact to verify | Planned fallback if denied |
|---|---|---|
| `Q-006` | Sandbox concurrent instance limit is 9 in practice | Lower `asg_max_size` to 3 |

## 5. How to check constraints during implementation

- `make tf-validate` and `make lint` MUST fail if a forbidden resource type appears. The repository includes a grep-based guard `scripts/check_constraints.sh` (`TST-CON-01`).
- Before any real `terraform apply` the operator MUST run `make tf-plan` and review it for forbidden resource types.

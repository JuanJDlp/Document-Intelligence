# Answered questions

Record of every sandbox question that has been closed, with the answer and the evidence that produced it. Each entry keeps its former `Q-NNN` ID, so a search finds it even after the row is removed from `open-questions.md`.

Evidence is listed as the command that was run and what it returned. Account IDs, keys, and session tokens are never recorded here. All tests were run on 2026-11-03 against the AWS Academy sandbox, role `voclabs`, region `us-east-1`.

---

## Q-002: Is Textract `AnalyzeExpense` allowed for the instance role?

- **Answer:** No. The instance role has no Textract permission.
- **Decision it led to:** OCR is Tesseract, run on the instance (`ADR-012`).
- **Evidence:**
  - `aws iam get-role-policy --role-name AmazonSSMRoleForInstancesQuickSetup --policy-name ReadParameterStore` returned `ssm:*` on `parameter/*`, and nothing else.
  - `aws iam get-role-policy --role-name ... --policy-name AttachRoleToInstance` returned three IAM and EC2 actions, and no Textract action.
  - `aws iam list-attached-role-policies --role-name ...` returned only `AmazonSSMManagedInstanceCore`. The policy document of that managed policy lists only `ssm:*`, `ssmmessages:*`, and `ec2messages:*` actions.

## Q-003: Is `cloudtrail:CreateTrail` allowed for the lab role?

- **Answer:** No. `CreateTrail` is denied.
- **Decision it led to:** `enable_cloudtrail` defaults to `false` and the blocker is documented (`INF-AUD-03`). The remaining audit path is the existing `describe-trails` read access.
- **Evidence:**
  - Created a temporary bucket and set a CloudTrail bucket policy. Both succeeded.
  - `aws cloudtrail create-trail --name ... --s3-bucket-name ...` returned `AccessDeniedException: ... not authorized to perform: cloudtrail:CreateTrail ... because no identity-based policy allows the cloudtrail:CreateTrail action`.
  - The temporary bucket was deleted afterwards.

## Q-004: Are NAT gateway and Elastic IP creation allowed?

- **Answer:** Yes. Both can be created.
- **Decision it led to:** The single NAT gateway design stays (`ADR-005`). No interface endpoints are needed for this reason.
- **Evidence:**
  - In a temporary VPC: `create-vpc`, `create-internet-gateway`, `attach-internet-gateway`, `create-subnet`, `allocate-address --domain vpc`, and `create-nat-gateway` all succeeded (NAT ID returned).
  - `aws ec2 describe-nat-gateways` reported `deleted` after `delete-nat-gateway`. The Elastic IP was released and the VPC resources were deleted.

## Q-005: Is CloudFront distribution creation allowed?

- **Answer:** Yes. A distribution can be created.
- **Decision it led to:** CloudFront with the `/api/*` origin stays (`ADR-030`).
- **Evidence:**
  - `aws cloudfront create-distribution` with `Enabled: false` returned a distribution ID with status `InProgress`.
  - **Still to clean up:** the distribution must be disabled and deleted after it deploys. It is a sandbox resource and will be removed with the sandbox.

## Q-007: Can Lambda run under the course roles?

- **Answer:** No. The instance role trusts only EC2.
- **Decision it led to:** No Lambda (`ADR-023`).
- **Evidence:**
  - `aws iam get-role --role-name AmazonSSMRoleForInstancesQuickSetup` returned an `AssumeRolePolicyDocument` with a single principal, `ec2.amazonaws.com`.
  - The brief states that new roles cannot be created (`CON-IAM-01`). That was not tested directly. Only the trust policy of the existing role was checked.

## Q-008: Which instance profile name exists in the sandbox?

- **Answer:** The profile name is not the course name. It is `<prefix>-SsmRoleInstanceProfile-<suffix>`, and the prefix and suffix change per lab. It wraps the role `AmazonSSMRoleForInstancesQuickSetup`, which does exist.
- **Decision it led to:** `instance_profile_name` has no default and is discovered each session by the `aws-sandbox` skill (`CON-IAM-03`).
- **Evidence:**
  - `aws iam list-instance-profiles --query "InstanceProfiles[?contains(InstanceProfileName,'SsmRoleInstanceProfile')].InstanceProfileName" --output text` returned one name of that form.
  - `aws iam get-instance-profile --instance-profile-name <that name>` listed `AmazonSSMRoleForInstancesQuickSetup` as its role.

## Q-009: Does `iam:GetRole` work?

- **Answer:** Yes, for the instance role. The brief's statement that it is denied is not true in this sandbox. It is denied for the lab role's own policies.
- **Decision it led to:** Terraform still makes no IAM calls (`CON-IAM-02`), by design. The brief statement is recorded as wrong in `02` section 0.1.
- **Evidence:**
  - `aws iam get-role --role-name AmazonSSMRoleForInstancesQuickSetup` returned the role.
  - `aws iam get-role --role-name voclabs` returned `AccessDenied ... with an explicit deny in an identity-based policy`.
  - `aws iam get-role-policy --role-name voclabs --policy-name Pvoclabs` was denied with the same message. The lab role's policy cannot be read.

## Q-010: Should the CloudWatch Logs agent ship application logs?

- **Answer:** Out of scope for v1. Logs go to the systemd journal. This is a scope decision, not a sandbox fact.
- **Decision it led to:** `OBS-LOG-01` in `09-security-observability.md`.
- **Evidence:** Not applicable. Decided by the team.

## SQS in the sandbox (no former question ID)

- **Answer:** Denied for the lab role.
- **Decision it led to:** No SQS. The `jobs` table is the queue (`ADR-010`).
- **Evidence:** `aws sqs list-queues --region us-east-1` returned `AccessDenied ... no identity-based policy allows the sqs:listqueues action`.

---

## Q-001: Can the instance role reach S3, DynamoDB, and SNS?

- **Answer:** Yes, through resource-based policies that name the role ARN. The role has no identity-based permission for those services, so the policy on the resource is the only grant.
- **Decision it led to:** Each bucket, table, and topic gets a policy naming `arn:aws:iam::<account>:role/AmazonSSMRoleForInstancesQuickSetup` (`ADR-033`).
- **Evidence (2026-11-03):**
  - Identity check from the instance, through SSM Run Command: `aws sts get-caller-identity` returned the assumed role `AmazonSSMRoleForInstancesQuickSetup/<instance>`. `s3api list-buckets`, `dynamodb list-tables`, `sns list-topics`, and `sqs list-queues` returned AccessDenied, with "no identity-based policy allows".
  - `ssm get-parameter` returned `ParameterNotFound`, which means the call was authorized.
  - After a bucket policy with `Principal.AWS = <role ARN>` on `s3:ListBucket`, `GetObject`, and `PutObject`: `aws s3 cp` from the instance exited 0, and `list-objects-v2` listed the object.
  - After an SNS topic policy with the same principal and `sns:Publish`: `aws sns publish` from the instance returned a MessageId.
  - After a DynamoDB resource policy with the same principal: `put-item` and `get-item` from the instance both exited 0.
  - A policy naming the account root (`arn:aws:iam::<account>:root`) did **not** grant access: the error was "no identity-based policy allows". A root principal delegates only to identities that already have permissions, so it is not used.

## Q-013: Can an Auto Scaling Group launch instances in the lab?

- **Answer:** Yes, when the root volume is `gp2`. The lab role has an explicit deny on `ec2:RunInstances` for volumes of type `gp3`. The default root volume of the Amazon Linux 2023 AMI is `gp3`, so launches without an explicit mapping fail.
- **Decision it led to:** The launch template sets the root volume explicitly to `gp2`, encrypted, 20 GB (`ADR-034`).
- **Evidence (2026-11-03):**
  - `aws ec2 run-instances --dry-run` with no block device mapping: `UnauthorizedOperation` on `volume/*`.
  - The same dry-run with `BlockDeviceMappings` of type `gp3`: `UnauthorizedOperation` on `volume/*`.
  - The same dry-run with type `gp2`, with and without `Encrypted: true`, with 8 GB and 20 GB, and with `KmsKeyId` `alias/aws/ebs`: all returned `DryRunOperation` (allowed).
  - A launch template with `gp2`, encrypted, 20 GB, and the instance profile, used by an Auto Scaling Group with min 0, max 1, desired 1: `describe-scaling-activities` showed `Successful`. The instance reached `InService` and `Healthy`, and SSM reported it `Online`.
  - The group was deleted with `--force-delete`. Its instance then reached `terminated`.
  - The earlier failure, `You are not authorized to use launch template`, came from validating the template with the `gp3` root volume.
  - Still not tested: the sandbox limit of 9 instances (`Q-006`).

---

## Q-006 and other items

- **Q-006** (9-instance limit) is still open in `open-questions.md`. The Service Quotas API is denied for the lab role.

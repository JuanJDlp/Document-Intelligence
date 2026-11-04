# Skill: AWS Academy sandbox session

Plain instructions for any AI agent (Claude Code, Codex, or others). No tool-specific features are required: you need a shell and file access.

Use this skill when:
- The user pastes AWS credentials from the lab ("AWS CLI" block with `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`).
- The user asks you to check, deploy to, or inspect the AWS sandbox.
- An AWS command fails with an expired or invalid token.

The sandbox is torn down and recreated often. Each new lab session brings new credentials, a new instance profile name, and possibly new resource IDs. Do not assume anything from a previous session.

## 1. Credentials: where they go and where they never go

- **Store** the three values only in `~/.aws/credentials`, under `[default]`. Region goes in `~/.aws/config`.
- **Never** write credentials into the repository, specs, docs, samples, logs, commit messages, pull requests, scripts, or your final report. If you find credentials in a project file, stop and tell the user.
- **Never** echo the values back in chat. Do not `cat` the credentials file.
- Temporary lab credentials still must never be committed. The repository `.gitignore` excludes common credential files, but the rule does not depend on it.

## 2. Procedure at the start of a session

1. Check whether the current session still works:
   ```sh
   scripts/aws_sandbox_check.sh
   ```
   - If it prints an ARN, the session is valid. Skip to step 4.
   - If it reports `SESSION INVALID OR EXPIRED`, go to step 2.
2. Write the new credentials. Use a shell heredoc with a restrictive umask. Do not read the file back.
   ```sh
   umask 077
   cat > ~/.aws/credentials <<'EOF_CREDS'
   [default]
   aws_access_key_id=<from user>
   aws_secret_access_key=<from user>
   aws_session_token=<from user>
   EOF_CREDS
   chmod 600 ~/.aws/credentials
   aws configure set region us-east-1
   ```
   If the file has other profiles, edit only the `[default]` block instead of overwriting the file.
3. Verify and run the read-only checks:
   ```sh
   scripts/aws_sandbox_check.sh
   ```
   Report the ARN, the region, and the OK/DENIED list to the user. Do not report credentials.
4. Discover the instance profile name. Names change per lab session, so never hard-code one:
   ```sh
   aws iam list-instance-profiles \
     --query "InstanceProfiles[?contains(InstanceProfileName, 'SsmRoleInstanceProfile')].InstanceProfileName" \
     --output text
   ```
   Write the result to `infra/terraform/terraform.tfvars` as `instance_profile_name`. That file is git-ignored. If the query returns nothing or several names, ask the user which one to use.

## 3. Rules while working in the sandbox

- **Read-only commands** (`describe`, `list`, `get`, `help`) may run without asking.
- **Anything that creates, changes, or deletes** resources needs explicit approval for that specific action in this conversation. This includes `terraform apply`, `make deploy`, `make publish`, `make bootstrap-artifacts`, `make deploy-frontend`, `make destroy`, and any `aws` write command. See `AGENTS.md` section 8.
- **Do not call IAM to create or modify anything**, and do not use Terraform data sources that read IAM roles (`CON-IAM-02`).
- **Expired token** (`ExpiredToken`, `InvalidClientTokenId`, "security token ... expired"): stop. Tell the user to restart the lab and paste new credentials. Do not try other credentials.
- **Access denied**: record the exact action that was denied and the service. Do not work around it with other permissions. Treat the result as a fact about the sandbox.
- **Region**: use `us-east-1` unless an ADR says otherwise. If calls fail with region errors, report that to the user.

## 4. Updating the harness with results

- A probe answers a question only if it tests what the question asks. The probes in `scripts/aws_sandbox_check.sh` run as the lab role, not as the EC2 instance profile. Probes of the instance role must run from the instance itself (SSM Run Command), as described in `answered-questions.md`.
- When a result answers an open question in `specs/open-questions.md`, delete that question's row. Write the consequence into the affected spec or ADR (`AGENTS.md` section 13).

## 5. Known facts from past sessions

- Lab role: `voclabs`. Sandbox ARNs look like `arn:aws:sts::<account>:assumed-role/voclabs/...`.
- `sqs:ListQueues` is denied for the lab role (see `specs/adr/ADR-010-dynamodb-jobs-as-queue.md`).
- The sandbox profile is named like `<prefix>-SsmRoleInstanceProfile-<suffix>`. It does not match the name in the course brief.
- The lab session lasts about two hours. The lab page shows "Session to end at". Tell the user when the session is near its end.
- The instance role `AmazonSSMRoleForInstancesQuickSetup` has `AmazonSSMManagedInstanceCore` and an inline `ssm:*` on parameters. It has no identity-based S3, DynamoDB, SNS, SQS, or Textract permission. S3, DynamoDB, and SNS work through resource policies that name the role ARN (`ADR-033`).
- The instance role trusts only `ec2.amazonaws.com`. Lambda cannot use it.
- `iam:GetRole` works for the instance role. It is denied for the lab role's own policies (explicit deny on `voclabs`).
- `ec2:RunInstances` is explicitly denied for `gp3` volumes for the lab role. A launch template must map the root volume as `gp2` (`ADR-034`).
- `servicequotas:GetServiceQuota` is denied.
- Dry-run probes (`--dry-run`) validate permissions without creating anything. Use them before any real call. Real tests that create resources need the user's approval.

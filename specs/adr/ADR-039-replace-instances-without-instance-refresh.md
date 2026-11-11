# ADR-039: Roll out new launch template versions by replacing instances, not by instance refresh

- **Status:** Accepted
- **Area:** Infrastructure / Compute

## Context
Verified 2026-11-10 during the first full deployment. Changing the launch template made Terraform call `autoscaling:StartInstanceRefresh`, which failed with `AccessDenied ... with an explicit deny in a service control policy`. The lab role cannot start an instance refresh. The launch template and the Auto Scaling group were still updated (the group pointed to the new template version), but the running instances kept the old version.

`autoscaling:TerminateInstanceInAutoScalingGroup` is allowed: on the same day it terminated two instances with `--no-should-decrement-desired-capacity`, and the group launched replacements from the new version.

## Decision
- The Auto Scaling group has no `instance_refresh` block. The group always uses the latest launch template version, so every new instance gets the new release.
- To roll out a new release or AMI, the operator replaces instances one at a time: terminate one instance with `aws autoscaling terminate-instance-in-auto-scaling-group --no-should-decrement-desired-capacity`, wait until its replacement is `healthy` in the target group, then do the next one. Each termination is an AWS write and needs approval (`AGENTS.md` section 8).

## Consequences
- A Terraform apply that changes the launch template no longer replaces running instances by itself.
- With two instances and one replacement at a time, one healthy target stays in service during the rollout.

Specs: `03-infrastructure.md` (`INF-EC2-04`), `docs/deployment-guide.md` section 5.

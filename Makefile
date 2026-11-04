# Single entry point for humans and agents (specs/10-testing-and-acceptance.md section 3).
# Targets that create or delete billable AWS resources are marked and need explicit approval.

TF_DIR := infra/terraform
TF_PLAN := $(TF_DIR)/.plan.tfplan

.PHONY: help lint tf-fmt tf-validate tf-plan tf-apply tf-destroy check-constraints

help:
	@echo "Targets: lint, tf-fmt, tf-validate, tf-plan, check-constraints"
	@echo "Approval required: tf-apply, tf-destroy"

lint: check-constraints tf-fmt

check-constraints:
	scripts/check_constraints.sh $(TF_DIR)

tf-fmt:
	terraform -chdir=$(TF_DIR) fmt -check -recursive

tf-validate:
	terraform -chdir=$(TF_DIR) init -backend=false -input=false >/dev/null
	terraform -chdir=$(TF_DIR) validate

tf-plan: check-constraints
	terraform -chdir=$(TF_DIR) plan -input=false -out=$(TF_PLAN)

# Billable: creates AWS resources. Run only with explicit approval.
tf-apply:
	terraform -chdir=$(TF_DIR) apply -input=false $(TF_PLAN)

# Destructive: deletes AWS resources. Run only with explicit approval.
tf-destroy:
	scripts/empty_buckets.sh
	terraform -chdir=$(TF_DIR) destroy -input=false

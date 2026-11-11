# Unified developer and operator entry point. Run from Ubuntu/WSL.
UV ?= uv
TF ?= terraform
VERSION ?= 1.0.0
TF_DIR := infra/terraform
.PHONY: setup lint format typecheck test test-ocr samples demo tf-validate tf-plan package package-check smoke bootstrap-artifacts publish deploy deploy-frontend up load destroy check-constraints
setup:
	$(UV) sync --locked
format:
	$(UV) run --no-sync ruff format app tests scripts
lint: check-constraints
	$(UV) run --no-sync ruff check app tests scripts
	$(UV) run --no-sync ruff format --check app tests scripts
	$(TF) -chdir=$(TF_DIR) fmt -check -recursive
	bash scripts/check_frontend.sh
	$(UV) run --no-sync python scripts/check_secrets.py
typecheck:
	$(UV) run --no-sync mypy --strict app/receipt_engine/src
	$(UV) run --no-sync mypy app/api/src app/worker/src
test:
	$(UV) run --no-sync pytest -m "not ocr"
test-ocr:
	$(UV) run --no-sync pytest -m ocr
samples:
	$(UV) run --no-sync python scripts/make_samples.py
demo:
	$(UV) run --no-sync python scripts/local_demo.py
check-constraints:
	bash scripts/check_constraints.sh $(TF_DIR)
tf-validate:
	$(TF) -chdir=$(TF_DIR) init -backend=false -input=false
	$(TF) -chdir=$(TF_DIR) validate
tf-plan: check-constraints
	$(TF) -chdir=$(TF_DIR) plan -input=false -out=.plan.tfplan
package:
	$(UV) run --no-sync python scripts/package_release.py --version $(VERSION)
package-check: package
	$(UV) run --no-sync python scripts/verify_package.py --version $(VERSION)
smoke:
	$(UV) run --no-sync python scripts/smoke_test.py
# AWS writes require explicit approval; these targets are never part of setup/test.
bootstrap-artifacts:
	$(TF) -chdir=$(TF_DIR) plan -target=module.buckets -out=.bootstrap.tfplan
	$(TF) -chdir=$(TF_DIR) apply .bootstrap.tfplan
publish:
	bash scripts/publish_release.sh $(VERSION)
deploy:
	$(TF) -chdir=$(TF_DIR) plan -var=release_version=$(VERSION) -var=asg_health_check_type=ELB -out=.release.tfplan
	$(TF) -chdir=$(TF_DIR) apply .release.tfplan
deploy-frontend:
	bash scripts/deploy_frontend.sh
# One-command deployment from a clean sandbox (TST-MK-15). Requires approval: creates billable resources.
up: package bootstrap-artifacts publish deploy deploy-frontend
	bash scripts/wait_healthy.sh
# Traffic simulation for the Auto Scaling demo (TST-MK-16). Requires approval: the ASG may launch instances.
load:
	LOAD_BASE_URL=https://$$($(TF) -chdir=$(TF_DIR) output -raw cloudfront_domain_name) \
	LOAD_ASG_NAME=$$($(TF) -chdir=$(TF_DIR) output -raw asg_name) \
	$(UV) run --no-sync python scripts/load_test.py
destroy:
	$(TF) -chdir=$(TF_DIR) plan -destroy
	bash scripts/empty_buckets.sh
	$(TF) -chdir=$(TF_DIR) destroy

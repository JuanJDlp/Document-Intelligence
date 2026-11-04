# Buckets are created through a CloudFormation stack (ADR-035).
# The provider's aws_s3_bucket resource reads Object Lock configuration on refresh, which the lab denies.
# CloudFormation creates the buckets without that read.

resource "aws_cloudformation_stack" "buckets" {
  name          = "${var.name}-buckets"
  template_body = file("${path.module}/templates/buckets.yaml")

  parameters = {
    Prefix    = var.name
    AccountId = var.account_id
  }

  timeout_in_minutes = 15
  on_failure         = "ROLLBACK"
}

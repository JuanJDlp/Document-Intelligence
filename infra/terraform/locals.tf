data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  name       = "${var.project}-${var.environment}"

  # Two AZs are required by the ALB, the Auto Scaling Group and the DB subnet group.
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # The instance role is pre-existing (CON-IAM-03). Its ARN is built from the account ID, never read from IAM.
  instance_role_arn = "arn:aws:iam::${local.account_id}:role/${var.instance_role_name}"

  common_tags = {
    Project     = "DocuProcessCloud"
    Environment = var.environment
    ManagedBy   = "terraform"
    Course      = "infraestructura-iii"
  }
}

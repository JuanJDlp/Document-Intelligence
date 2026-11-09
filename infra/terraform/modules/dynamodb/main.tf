# Document and job tables (DAT-DDB-*). Access for the instance role is granted by resource policies (INF-RPOL-03).

resource "aws_dynamodb_table" "documents" {
  name         = "${var.name}-documents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document_id"

  attribute {
    name = "document_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_user_created"
    hash_key        = "user_id"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }

  deletion_protection_enabled = false

  tags = { Name = "${var.name}-documents" }
}

resource "aws_dynamodb_table" "jobs" {
  name         = "${var.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "available_at"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_status_available"
    hash_key        = "status"
    range_key       = "available_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }

  deletion_protection_enabled = false

  tags = { Name = "${var.name}-jobs" }
}

resource "aws_dynamodb_resource_policy" "documents" {
  resource_arn = aws_dynamodb_table.documents.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "InstanceRoleDocumentsAccess"
      Effect    = "Allow"
      Principal = { AWS = var.instance_role_arn }
      Action = [
        "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
        "dynamodb:Query", "dynamodb:DescribeTable", "dynamodb:Scan",
      ]
      Resource = [
        aws_dynamodb_table.documents.arn,
        "${aws_dynamodb_table.documents.arn}/index/*",
      ]
    }]
  })
}

resource "aws_dynamodb_resource_policy" "jobs" {
  resource_arn = aws_dynamodb_table.jobs.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "InstanceRoleJobsAccess"
      Effect    = "Allow"
      Principal = { AWS = var.instance_role_arn }
      Action = [
        "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
        "dynamodb:Query", "dynamodb:DescribeTable",
      ]
      Resource = [
        aws_dynamodb_table.jobs.arn,
        "${aws_dynamodb_table.jobs.arn}/index/*",
      ]
    }]
  })
}

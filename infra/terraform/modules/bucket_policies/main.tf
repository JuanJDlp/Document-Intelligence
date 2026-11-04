# Bucket policies for the instance role (INF-RPOL-02, ADR-033). Bucket creation lives in modules/buckets (ADR-035).

resource "aws_s3_bucket_policy" "uploads" {
  bucket = var.uploads_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "InstanceRoleObjectAccess"
        Effect    = "Allow"
        Principal = { AWS = var.instance_role_arn }
        Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource  = "${var.uploads_bucket_arn}/*"
      },
      {
        Sid       = "InstanceRoleBucketList"
        Effect    = "Allow"
        Principal = { AWS = var.instance_role_arn }
        Action    = ["s3:ListBucket"]
        Resource  = var.uploads_bucket_arn
      },
    ]
  })
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = var.artifacts_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "InstanceRoleReadRelease"
        Effect    = "Allow"
        Principal = { AWS = var.instance_role_arn }
        Action    = ["s3:GetObject"]
        Resource  = "${var.artifacts_bucket_arn}/releases/*"
      },
      {
        Sid       = "InstanceRoleListReleases"
        Effect    = "Allow"
        Principal = { AWS = var.instance_role_arn }
        Action    = ["s3:ListBucket"]
        Resource  = var.artifacts_bucket_arn
      },
    ]
  })
}

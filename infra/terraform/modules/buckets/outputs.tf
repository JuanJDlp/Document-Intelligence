output "uploads_bucket_name" {
  description = "Uploads bucket name."
  value       = aws_cloudformation_stack.buckets.outputs["UploadsBucketName"]
}

output "uploads_bucket_arn" {
  description = "Uploads bucket ARN."
  value       = aws_cloudformation_stack.buckets.outputs["UploadsBucketArn"]
}

output "artifacts_bucket_name" {
  description = "Artifacts bucket name."
  value       = aws_cloudformation_stack.buckets.outputs["ArtifactsBucketName"]
}

output "artifacts_bucket_arn" {
  description = "Artifacts bucket ARN."
  value       = aws_cloudformation_stack.buckets.outputs["ArtifactsBucketArn"]
}

output "frontend_bucket_name" {
  description = "Frontend bucket name."
  value       = aws_cloudformation_stack.buckets.outputs["FrontendBucketName"]
}

output "frontend_bucket_arn" {
  description = "Frontend bucket ARN."
  value       = aws_cloudformation_stack.buckets.outputs["FrontendBucketArn"]
}

output "audit_logs_bucket_name" {
  description = "Audit logs bucket name."
  value       = aws_cloudformation_stack.buckets.outputs["AuditLogsBucketName"]
}

output "audit_logs_bucket_arn" {
  description = "Audit logs bucket ARN."
  value       = aws_cloudformation_stack.buckets.outputs["AuditLogsBucketArn"]
}

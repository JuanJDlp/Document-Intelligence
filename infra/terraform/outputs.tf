output "cloudfront_domain_name" {
  description = "Public entry point. Open https://<this value> in the browser."
  value       = module.frontend.domain_name
}

output "alb_dns_name" {
  description = "ALB DNS name (origin behind CloudFront /api/*)."
  value       = module.alb.dns_name
}

output "frontend_bucket_name" {
  description = "Frontend bucket for scripts/deploy_frontend.sh."
  value       = module.buckets.frontend_bucket_name
}

output "artifacts_bucket_name" {
  description = "Release artifacts bucket for scripts/publish_release.sh."
  value       = module.buckets.artifacts_bucket_name
}

output "uploads_bucket_name" {
  description = "Uploads bucket."
  value       = module.buckets.uploads_bucket_name
}

output "documents_table_name" {
  description = "DynamoDB documents table."
  value       = module.dynamodb.documents_table_name
}

output "jobs_table_name" {
  description = "DynamoDB jobs table."
  value       = module.dynamodb.jobs_table_name
}

output "db_endpoint" {
  description = "RDS hostname (no password)."
  value       = module.database.endpoint
}

output "db_name" {
  description = "RDS database name."
  value       = module.database.db_name
}

output "db_password_parameter_name" {
  description = "SSM parameter that holds the DB password. The value is never output."
  value       = module.database.password_parameter_name
}

output "processing_events_topic_arn" {
  description = "SNS topic for processing notifications."
  value       = module.messaging.processing_topic_arn
}

output "asg_name" {
  description = "Auto Scaling Group name."
  value       = module.compute.asg_name
}

output "instance_role_arn" {
  description = "Instance role ARN used by resource policies (ADR-033)."
  value       = local.instance_role_arn
}

output "cloudfront_distribution_id" {
  description = "Distribution ID for frontend invalidations."
  value       = module.frontend.distribution_id
}

output "audit_logs_bucket_name" {
  description = "Audit bucket for approved teardown."
  value       = module.buckets.audit_logs_bucket_name
}

output "target_group_arn" {
  description = "API target group. Used by scripts/wait_healthy.sh."
  value       = module.alb.target_group_arn
}

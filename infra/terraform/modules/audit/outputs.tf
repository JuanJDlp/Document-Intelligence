output "trail_name" {
  description = "CloudTrail trail name, or empty when disabled."
  value       = var.enabled ? aws_cloudtrail.this[0].name : ""
}

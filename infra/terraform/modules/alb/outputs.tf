output "dns_name" {
  description = "ALB DNS name, used as the CloudFront origin for /api/*."
  value       = aws_lb.this.dns_name
}

output "arn" {
  description = "ALB ARN."
  value       = aws_lb.this.arn
}

output "arn_suffix" {
  description = "ALB ARN suffix, used by CloudWatch dimensions."
  value       = aws_lb.this.arn_suffix
}

output "target_group_arn" {
  description = "API target group ARN."
  value       = aws_lb_target_group.api.arn
}

output "target_group_arn_suffix" {
  description = "API target group ARN suffix, used by CloudWatch dimensions."
  value       = aws_lb_target_group.api.arn_suffix
}

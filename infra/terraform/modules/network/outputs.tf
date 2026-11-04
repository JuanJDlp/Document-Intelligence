output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB)."
  value       = aws_subnet.public[*].id
}

output "app_subnet_ids" {
  description = "Private application subnet IDs (ASG)."
  value       = aws_subnet.app[*].id
}

output "db_subnet_group_name" {
  description = "DB subnet group name (RDS)."
  value       = aws_db_subnet_group.this.name
}

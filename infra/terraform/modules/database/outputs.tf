output "endpoint" {
  description = "RDS hostname (no port)."
  value       = aws_db_instance.this.address
}

output "identifier" {
  description = "RDS instance identifier, used by CloudWatch dimensions."
  value       = aws_db_instance.this.identifier
}

output "db_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "username" {
  description = "Master username."
  value       = aws_db_instance.this.username
}

output "password_parameter_name" {
  description = "SSM parameter name that holds the master password. The value is never output."
  value       = aws_ssm_parameter.db_password.name
}

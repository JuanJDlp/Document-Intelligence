output "documents_table_name" {
  description = "Documents table name."
  value       = aws_dynamodb_table.documents.name
}

output "jobs_table_name" {
  description = "Jobs table name."
  value       = aws_dynamodb_table.jobs.name
}

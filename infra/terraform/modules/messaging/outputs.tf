output "processing_topic_arn" {
  description = "Processing events topic ARN."
  value       = aws_sns_topic.processing.arn
}

output "ops_alarms_topic_arn" {
  description = "Ops alarms topic ARN."
  value       = aws_sns_topic.ops_alarms.arn
}

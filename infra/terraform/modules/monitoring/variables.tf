variable "name" {
  description = "Name prefix, also used as the dashboard name."
  type        = string
}

variable "region" {
  description = "AWS region for dashboard widgets."
  type        = string
}

variable "asg_name" {
  description = "Auto Scaling Group name."
  type        = string
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix."
  type        = string
}

variable "target_group_arn_suffix" {
  description = "API target group ARN suffix."
  type        = string
}

variable "rds_identifier" {
  description = "RDS instance identifier."
  type        = string
}

variable "ops_topic_arn" {
  description = "SNS topic for alarm notifications."
  type        = string
}

variable "cpu_threshold" {
  description = "Average CPU percent for asg-cpu-high."
  type        = number
}

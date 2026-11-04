variable "name" {
  description = "Name prefix."
  type        = string
}

variable "region" {
  description = "AWS region, used to build the S3 regional domain name."
  type        = string
}

variable "frontend_bucket_name" {
  description = "Frontend bucket name, created by modules/buckets."
  type        = string
}

variable "frontend_bucket_arn" {
  description = "Frontend bucket ARN, created by modules/buckets."
  type        = string
}

variable "alb_dns_name" {
  description = "ALB DNS name used as the /api/* origin."
  type        = string
}

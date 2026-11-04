variable "name" {
  description = "Name prefix."
  type        = string
}

variable "account_id" {
  description = "AWS account ID, used in the policy."
  type        = string
}

variable "bucket_name" {
  description = "Audit logs bucket name, created by modules/buckets."
  type        = string
}

variable "bucket_arn" {
  description = "Audit logs bucket ARN, created by modules/buckets."
  type        = string
}

variable "enabled" {
  description = "Create the trail and its bucket policy. False when cloudtrail:CreateTrail is denied."
  type        = bool
}

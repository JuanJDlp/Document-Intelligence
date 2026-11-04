variable "instance_role_arn" {
  description = "ARN of the instance role granted access by bucket policy (ADR-033)."
  type        = string
}

variable "uploads_bucket_name" {
  description = "Uploads bucket name."
  type        = string
}

variable "uploads_bucket_arn" {
  description = "Uploads bucket ARN."
  type        = string
}

variable "artifacts_bucket_name" {
  description = "Artifacts bucket name."
  type        = string
}

variable "artifacts_bucket_arn" {
  description = "Artifacts bucket ARN."
  type        = string
}

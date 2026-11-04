variable "name" {
  description = "Name prefix."
  type        = string
}

variable "instance_role_arn" {
  description = "ARN of the instance role allowed to publish (ADR-033)."
  type        = string
}

variable "alert_email" {
  description = "Email subscriber for both topics. Empty disables subscriptions. The recipient must confirm."
  type        = string
  default     = ""
}

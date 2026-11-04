variable "name" {
  description = "Name prefix."
  type        = string
}

variable "instance_role_arn" {
  description = "ARN of the instance role granted access by resource policy (ADR-033)."
  type        = string
}

variable "name" {
  description = "Name prefix."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Two public subnet IDs."
  type        = list(string)
}

variable "security_group_id" {
  description = "ALB security group ID."
  type        = string
}

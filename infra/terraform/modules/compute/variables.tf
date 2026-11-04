variable "name" {
  description = "Name prefix."
  type        = string
}

variable "instance_profile_name" {
  description = "Pre-existing SSM instance profile name (CON-IAM-03)."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
}

variable "root_volume_size_gb" {
  description = "Root volume size in GB."
  type        = number
}

variable "security_group_id" {
  description = "Application instances security group ID."
  type        = string
}

variable "subnet_ids" {
  description = "Two private application subnet IDs."
  type        = list(string)
}

variable "target_group_arns" {
  description = "Target groups that receive traffic from the ALB."
  type        = list(string)
}

variable "min_size" {
  description = "ASG minimum size."
  type        = number
}

variable "max_size" {
  description = "ASG maximum size."
  type        = number
}

variable "health_check_type" {
  description = "EC2 or ELB."
  type        = string
}

variable "user_data" {
  description = "Rendered bootstrap script. Contains no secrets (INF-UD-05)."
  type        = string
}

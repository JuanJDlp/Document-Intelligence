variable "name" {
  description = "Name prefix."
  type        = string
}

variable "project" {
  description = "Project name, used in SSM parameter paths."
  type        = string
}

variable "environment" {
  description = "Environment name, used in SSM parameter paths."
  type        = string
}

variable "engine_version" {
  description = "MySQL version."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
}

variable "allocated_storage_gb" {
  description = "Allocated storage in GB."
  type        = number
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "docuprocess"
}

variable "db_username" {
  description = "Master username."
  type        = string
  default     = "docuprocess_admin"
}

variable "db_subnet_group_name" {
  description = "DB subnet group name."
  type        = string
}

variable "security_group_id" {
  description = "Security group allowing MySQL from application instances only."
  type        = string
}

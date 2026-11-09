variable "region" {
  description = "AWS region. The sandbox and the course diagram use us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "docuprocess"
}

variable "environment" {
  description = "Environment name. Only sandbox is valid for this course project."
  type        = string
  default     = "sandbox"

  validation {
    condition     = var.environment == "sandbox"
    error_message = "environment must be \"sandbox\"."
  }
}

variable "instance_profile_name" {
  description = "Name of the pre-existing SSM instance profile. Discovered per lab session (skills/aws-sandbox). Never created here (CON-IAM-03)."
  type        = string
}

variable "instance_role_name" {
  description = "Name of the IAM role inside the instance profile. Used only to build the role ARN for resource policies (ADR-033)."
  type        = string
  default     = "AmazonSSMRoleForInstancesQuickSetup"
}

variable "vpc_cidr" {
  description = "VPC CIDR block (INF-NET-01)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "instance_type" {
  description = "EC2 instance type for API and worker instances. Sandbox allows t2/t3 nano to medium (CON-EC2-01)."
  type        = string
  default     = "t3.micro"

  validation {
    condition     = can(regex("^t[23]\\.(nano|micro|small|medium)$", var.instance_type))
    error_message = "instance_type must be t2 or t3, between nano and medium."
  }
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size. Sandbox limit is 35 GB (CON-EC2-03)."
  type        = number
  default     = 20

  validation {
    condition     = var.root_volume_size_gb >= 8 && var.root_volume_size_gb <= 35
    error_message = "root_volume_size_gb must be between 8 and 35."
  }
}

variable "asg_min_size" {
  description = "Minimum instances in the Auto Scaling Group (INF-ASG-01)."
  type        = number
  default     = 2
}

variable "asg_max_size" {
  description = "Maximum instances in the Auto Scaling Group (CON-EC2-02)."
  type        = number
  default     = 4

  validation {
    condition     = var.asg_max_size <= 4
    error_message = "asg_max_size must be 4 or less (CON-EC2-02)."
  }
}

variable "asg_health_check_type" {
  description = "Application-release health checks (ELB). Empty releases always use EC2 checks."
  type        = string
  default     = "ELB"

  validation {
    condition     = contains(["EC2", "ELB"], var.asg_health_check_type)
    error_message = "asg_health_check_type must be EC2 or ELB."
  }
}

variable "release_version" {
  description = "Application release to install on instances. Empty means infrastructure only: instances boot without starting the application (INF-UD-03)."
  type        = string
  default     = ""
}

variable "db_instance_class" {
  description = "RDS instance class. Sandbox allows db.t2/db.t3 micro to medium (CON-RDS-01)."
  type        = string
  default     = "db.t3.micro"

  validation {
    condition     = can(regex("^db\\.t[23]\\.(micro|small|medium)$", var.db_instance_class))
    error_message = "db_instance_class must be db.t2 or db.t3, between micro and medium."
  }
}

variable "db_allocated_storage_gb" {
  description = "RDS storage in GB, gp2 (CON-RDS-03, max 100)."
  type        = number
  default     = 20

  validation {
    condition     = var.db_allocated_storage_gb >= 20 && var.db_allocated_storage_gb <= 100
    error_message = "db_allocated_storage_gb must be between 20 and 100."
  }
}

variable "db_engine_version" {
  description = "MySQL major.minor version (ADR-003)."
  type        = string
  default     = "8.0"
}

variable "alert_email" {
  description = "Email for SNS subscriptions. Empty means no subscription. The recipient must confirm the subscription."
  type        = string
  default     = ""
}

variable "ocr_provider" {
  description = "OCR provider used by the application. Only tesseract in v1 (ADR-012)."
  type        = string
  default     = "tesseract"

  validation {
    condition     = var.ocr_provider == "tesseract"
    error_message = "ocr_provider must be \"tesseract\" in v1 (ADR-012)."
  }
}

variable "max_upload_bytes" {
  description = "Maximum upload size in bytes (ADR-013)."
  type        = number
  default     = 5242880
}

variable "enable_cloudtrail" {
  description = "Create the CloudTrail trail. The lab denies cloudtrail:CreateTrail (answered-questions.md, Q-003), so this defaults to false."
  type        = bool
  default     = false
}

variable "cloudwatch_cpu_alarm_threshold" {
  description = "Average CPU percent that triggers asg-cpu-high (INF-MON-01)."
  type        = number
  default     = 80
}

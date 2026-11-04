variable "name" {
  description = "Name prefix used for bucket names, for example docuprocess-sandbox."
  type        = string
}

variable "account_id" {
  description = "AWS account ID, used to make bucket names globally unique."
  type        = string
}

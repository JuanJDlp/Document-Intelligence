# Root composition. Modules follow specs/03-infrastructure.md.
# Hybrid layout (ADR-035): buckets come from CloudFormation, everything else from Terraform.

module "network" {
  source = "./modules/network"

  name     = local.name
  region   = var.region
  vpc_cidr = var.vpc_cidr
  azs      = local.azs
}

module "security" {
  source = "./modules/security"

  name   = local.name
  vpc_id = module.network.vpc_id
}

module "buckets" {
  source = "./modules/buckets"

  name       = local.name
  account_id = local.account_id
}

module "bucket_policies" {
  source = "./modules/bucket_policies"

  instance_role_arn     = local.instance_role_arn
  uploads_bucket_name   = module.buckets.uploads_bucket_name
  uploads_bucket_arn    = module.buckets.uploads_bucket_arn
  artifacts_bucket_name = module.buckets.artifacts_bucket_name
  artifacts_bucket_arn  = module.buckets.artifacts_bucket_arn
}

module "dynamodb" {
  source = "./modules/dynamodb"

  name              = local.name
  instance_role_arn = local.instance_role_arn
}

module "messaging" {
  source = "./modules/messaging"

  name              = local.name
  instance_role_arn = local.instance_role_arn
  alert_email       = var.alert_email
}

module "database" {
  source = "./modules/database"

  name                 = local.name
  project              = var.project
  environment          = var.environment
  engine_version       = var.db_engine_version
  instance_class       = var.db_instance_class
  allocated_storage_gb = var.db_allocated_storage_gb
  db_subnet_group_name = module.network.db_subnet_group_name
  security_group_id    = module.security.db_security_group_id
}

module "alb" {
  source = "./modules/alb"

  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.security.alb_security_group_id
}

module "frontend" {
  source = "./modules/frontend"

  name                 = local.name
  region               = var.region
  frontend_bucket_name = module.buckets.frontend_bucket_name
  frontend_bucket_arn  = module.buckets.frontend_bucket_arn
  alb_dns_name         = module.alb.dns_name
}

module "compute" {
  source = "./modules/compute"

  name                  = local.name
  instance_profile_name = var.instance_profile_name
  instance_type         = var.instance_type
  root_volume_size_gb   = var.root_volume_size_gb
  security_group_id     = module.security.app_security_group_id
  subnet_ids            = module.network.app_subnet_ids
  target_group_arns     = [module.alb.target_group_arn]
  min_size              = var.asg_min_size
  max_size              = var.asg_max_size
  health_check_type     = var.asg_health_check_type

  user_data = templatefile("${path.module}/templates/userdata.sh.tftpl", {
    region                = var.region
    release_version       = var.release_version
    artifacts_bucket      = module.buckets.artifacts_bucket_name
    db_host               = module.database.endpoint
    db_name               = module.database.db_name
    db_user               = module.database.username
    db_password_parameter = module.database.password_parameter_name
    uploads_bucket        = module.buckets.uploads_bucket_name
    documents_table       = module.dynamodb.documents_table_name
    jobs_table            = module.dynamodb.jobs_table_name
    processing_topic_arn  = module.messaging.processing_topic_arn
    cors_origin           = "https://${module.frontend.domain_name}"
    max_upload_bytes      = var.max_upload_bytes
    ocr_provider          = var.ocr_provider
  })
}

module "monitoring" {
  source = "./modules/monitoring"

  name                    = local.name
  region                  = var.region
  asg_name                = module.compute.asg_name
  alb_arn_suffix          = module.alb.arn_suffix
  target_group_arn_suffix = module.alb.target_group_arn_suffix
  rds_identifier          = module.database.identifier
  ops_topic_arn           = module.messaging.ops_alarms_topic_arn
  cpu_threshold           = var.cloudwatch_cpu_alarm_threshold
}

module "audit" {
  source = "./modules/audit"

  name        = local.name
  account_id  = local.account_id
  bucket_name = module.buckets.audit_logs_bucket_name
  bucket_arn  = module.buckets.audit_logs_bucket_arn
  enabled     = var.enable_cloudtrail
}

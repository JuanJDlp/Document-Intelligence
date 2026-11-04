# RDS MySQL, Single-AZ (INF-RDS-*, ADR-003). The master password is generated and stored in SSM (INF-RDS-06).

resource "random_password" "master" {
  length  = 24
  special = false
}

resource "aws_db_instance" "this" {
  identifier = "${var.name}-db"

  engine         = "mysql"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp2"
  storage_encrypted = false # KMS is list-only in the sandbox (CON-KMS-01, ADR-032)

  db_name  = var.db_name
  username = var.db_username
  password = random_password.master.result

  multi_az               = false # CON-RDS-02
  publicly_accessible    = false # CON-RDS-05
  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [var.security_group_id]

  backup_retention_period    = 1
  skip_final_snapshot        = true
  deletion_protection        = false
  auto_minor_version_upgrade = true
  apply_immediately          = true

  tags = { Name = "${var.name}-db" }
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/${var.project}/${var.environment}/db/password"
  description = "RDS master password for the DocuProcess database"
  type        = "SecureString"
  value       = random_password.master.result

  tags = { Name = "${var.name}-db-password" }
}

# Launch template and Auto Scaling Group for API and worker instances (INF-EC2-*, INF-ASG-*).

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"] # CON-EC2-04

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.name}-app-"
  description   = "API and worker instances"
  image_id      = data.aws_ami.al2023.id
  instance_type = var.instance_type

  # Root volume is mapped explicitly as gp2: the lab denies gp3 volumes (ADR-034).
  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.root_volume_size_gb
      volume_type           = "gp2"
      encrypted             = true
      delete_on_termination = true
    }
  }

  iam_instance_profile {
    name = var.instance_profile_name # CON-IAM-03, never created here
  }

  vpc_security_group_ids = [var.security_group_id]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  user_data = base64encode(var.user_data)

  update_default_version = true

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.name}-app" }
  }

  tag_specifications {
    resource_type = "volume"
    tags          = { Name = "${var.name}-app-root" }
  }
}

resource "aws_autoscaling_group" "app" {
  name                = "${var.name}-app"
  min_size            = var.min_size
  max_size            = var.max_size
  desired_capacity    = var.min_size
  vpc_zone_identifier = var.subnet_ids
  target_group_arns   = var.target_group_arns

  health_check_type         = var.health_check_type # INF-ASG-03
  health_check_grace_period = 300

  # Do not block Terraform until instances are healthy: the application may not be deployed yet.
  wait_for_capacity_timeout = "0"

  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }

  tag {
    key                 = "Name"
    value               = "${var.name}-app"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Target tracking on average CPU (INF-ASG-04).
resource "aws_autoscaling_policy" "cpu_target" {
  name                   = "${var.name}-cpu-target-60"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }

    target_value     = 60
    disable_scale_in = false
  }

  estimated_instance_warmup = 180
}

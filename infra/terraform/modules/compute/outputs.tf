output "asg_name" {
  description = "Auto Scaling Group name."
  value       = aws_autoscaling_group.app.name
}

output "ami_id" {
  description = "AMI used by the launch template."
  value       = data.aws_ami.ubuntu.id
}

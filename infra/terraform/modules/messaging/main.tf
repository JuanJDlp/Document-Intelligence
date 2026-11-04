# SNS topics (INF-SNS-*). The processing topic grants the instance role sns:Publish (INF-RPOL-04).

resource "aws_sns_topic" "processing" {
  name = "${var.name}-processing-events"

  tags = { Name = "${var.name}-processing-events" }
}

resource "aws_sns_topic_policy" "processing" {
  arn = aws_sns_topic.processing.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "InstanceRolePublish"
      Effect    = "Allow"
      Principal = { AWS = var.instance_role_arn }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.processing.arn
    }]
  })
}

resource "aws_sns_topic" "ops_alarms" {
  name = "${var.name}-ops-alarms"

  tags = { Name = "${var.name}-ops-alarms" }
}

resource "aws_sns_topic_subscription" "processing_email" {
  count = var.alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.processing.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "ops_email" {
  count = var.alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.ops_alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

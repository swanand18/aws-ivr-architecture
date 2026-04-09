# terraform/modules/sns/main.tf

resource "aws_sns_topic" "alerts" {
  name              = "${var.name_prefix}-ivr-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = { Name = "${var.name_prefix}-ivr-alerts" }
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

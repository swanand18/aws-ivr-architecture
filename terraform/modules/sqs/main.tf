# terraform/modules/sqs/main.tf

resource "aws_sqs_queue" "callback_dlq" {
  name              = "${var.name_prefix}-callback-dlq"
  kms_master_key_id = var.kms_key_arn
  tags              = { Name = "${var.name_prefix}-callback-dlq" }
}

resource "aws_sqs_queue" "callback" {
  name                       = "${var.name_prefix}-callback-queue"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.callback_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.name_prefix}-callback-queue" }
}

# terraform/modules/kms/main.tf

resource "aws_kms_key" "ivr" {
  description             = "KMS key for IVR platform encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:root" }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda and DynamoDB"
        Effect = "Allow"
        Principal = { Service = ["lambda.amazonaws.com", "dynamodb.amazonaws.com", "s3.amazonaws.com"] }
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = "*"
      }
    ]
  })

  tags = { Name = "${var.name_prefix}-ivr-kms" }
}

resource "aws_kms_alias" "ivr" {
  name          = "alias/${var.name_prefix}-ivr"
  target_key_id = aws_kms_key.ivr.key_id
}

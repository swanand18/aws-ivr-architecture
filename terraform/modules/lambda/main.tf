# terraform/modules/lambda/main.tf

locals {
  functions = {
    ivr-handler = {
      description = "Main IVR entry-point — handles inbound Connect events"
      handler     = "handler.lambda_handler"
      timeout     = 10
      memory      = 256
    }
    menu-router = {
      description = "DTMF / speech intent routing engine"
      handler     = "handler.lambda_handler"
      timeout     = 8
      memory      = 128
    }
    crm-lookup = {
      description = "Caller identification via DynamoDB + external CRM"
      handler     = "handler.lambda_handler"
      timeout     = 10
      memory      = 256
    }
    callback-scheduler = {
      description = "Schedules callback via SQS"
      handler     = "handler.lambda_handler"
      timeout     = 8
      memory      = 128
    }
    recording-processor = {
      description = "Post-call recording processor — triggers Transcribe"
      handler     = "handler.lambda_handler"
      timeout     = 30
      memory      = 512
    }
  }

  common_env = {
    ENVIRONMENT             = var.environment
    REGION                  = var.region
    LOG_LEVEL               = "INFO"
    CALLER_PROFILES_TABLE   = var.caller_profiles_table
    MENU_CONFIG_TABLE       = var.menu_config_table
    CALL_LOGS_TABLE         = var.call_logs_table
    AUDIO_BUCKET            = var.audio_bucket
    RECORDINGS_BUCKET       = var.recordings_bucket
    CALLBACK_QUEUE_URL      = var.callback_queue_url
    ALERT_TOPIC_ARN         = var.alert_topic_arn
  }
}

# ── IAM Role (one per function) ───────────────────────────────
resource "aws_iam_role" "lambda" {
  for_each = local.functions

  name = "${var.name_prefix}-lambda-${each.key}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  for_each   = local.functions
  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ── Shared policy: DynamoDB + S3 + SQS + SNS + Transcribe ─────
resource "aws_iam_role_policy" "ivr_permissions" {
  for_each = local.functions
  name     = "${var.name_prefix}-${each.key}-policy"
  role     = aws_iam_role.lambda[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:Query", "dynamodb:Scan", "dynamodb:DeleteItem"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.region}:${var.account_id}:table/${var.caller_profiles_table}",
          "arn:aws:dynamodb:${var.region}:${var.account_id}:table/${var.caller_profiles_table}/index/*",
          "arn:aws:dynamodb:${var.region}:${var.account_id}:table/${var.menu_config_table}",
          "arn:aws:dynamodb:${var.region}:${var.account_id}:table/${var.call_logs_table}",
        ]
      },
      {
        Sid    = "S3"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.audio_bucket}",
          "arn:aws:s3:::${var.audio_bucket}/*",
          "arn:aws:s3:::${var.recordings_bucket}",
          "arn:aws:s3:::${var.recordings_bucket}/*",
        ]
      },
      {
        Sid    = "SQS"
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = ["arn:aws:sqs:${var.region}:${var.account_id}:*"]
      },
      {
        Sid    = "SNS"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = [var.alert_topic_arn]
      },
      {
        Sid    = "Transcribe"
        Effect = "Allow"
        Action = ["transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"]
        Resource = ["*"]
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

# ── Package & Deploy Lambdas ──────────────────────────────────
data "archive_file" "lambda_zip" {
  for_each    = local.functions
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/${each.key}"
  output_path = "${path.module}/../../../lambda/.dist/${each.key}.zip"
}

resource "aws_lambda_function" "this" {
  for_each = local.functions

  function_name    = "${var.name_prefix}-${each.key}"
  description      = each.value.description
  role             = aws_iam_role.lambda[each.key].arn
  handler          = each.value.handler
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip[each.key].output_path
  source_code_hash = data.archive_file.lambda_zip[each.key].output_base64sha256
  timeout          = each.value.timeout
  memory_size      = each.value.memory

  environment {
    variables = local.common_env
  }

  kms_key_arn = var.kms_key_arn

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name     = "${var.name_prefix}-${each.key}"
    Function = each.key
  }

  depends_on = [aws_iam_role_policy_attachment.basic_execution]
}

# ── CloudWatch Log Groups ─────────────────────────────────────
resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.functions
  name              = "/aws/lambda/${var.name_prefix}-${each.key}"
  retention_in_days = 30
  kms_key_id        = var.kms_key_arn
}

# ── S3 Trigger for recording-processor ───────────────────────
resource "aws_lambda_permission" "s3_invoke_recording_processor" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this["recording-processor"].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.recordings_bucket}"
}

# ── Connect invoke permissions ────────────────────────────────
resource "aws_lambda_permission" "connect_invoke" {
  for_each      = { for k, v in local.functions : k => v if k != "recording-processor" }
  statement_id  = "AllowConnectInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this[each.key].function_name
  principal     = "connect.amazonaws.com"
  source_arn    = "arn:aws:connect:${var.region}:${var.account_id}:instance/*"
}

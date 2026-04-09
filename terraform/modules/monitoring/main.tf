# terraform/modules/monitoring/main.tf

# ── CloudWatch Dashboard ──────────────────────────────────────
resource "aws_cloudwatch_dashboard" "ivr" {
  dashboard_name = "${var.name_prefix}-ivr-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "Lambda Invocations & Errors"
          period = 300
          stat   = "Sum"
          metrics = [
            for fn_name in values(var.lambda_function_names) : ["AWS/Lambda", "Invocations", "FunctionName", fn_name]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "Lambda Duration (P99)"
          period = 300
          stat   = "p99"
          metrics = [
            for fn_name in values(var.lambda_function_names) : ["AWS/Lambda", "Duration", "FunctionName", fn_name]
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title   = "Connect Concurrent Calls"
          period  = 60
          stat    = "Maximum"
          metrics = [["AWS/Connect", "ConcurrentCalls", "InstanceId", var.connect_instance_id]]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title   = "Callback Queue Depth"
          period  = 60
          stat    = "Maximum"
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.callback_queue_name]]
        }
      }
    ]
  })
}

# ── Lambda Error Alarms ───────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.lambda_function_names

  alarm_name          = "${var.name_prefix}-${each.key}-errors"
  alarm_description   = "Lambda ${each.key} error rate > 5 in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = [var.alert_topic_arn]
  ok_actions    = [var.alert_topic_arn]

  tags = { Name = "${var.name_prefix}-${each.key}-errors" }
}

# ── Lambda Throttle Alarms ────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = var.lambda_function_names

  alarm_name          = "${var.name_prefix}-${each.key}-throttles"
  alarm_description   = "Lambda ${each.key} throttles > 0"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.value
  }

  alarm_actions = [var.alert_topic_arn]

  tags = { Name = "${var.name_prefix}-${each.key}-throttles" }
}

# ── Connect Queue Wait Time Alarm ─────────────────────────────
resource "aws_cloudwatch_metric_alarm" "connect_queue_wait" {
  alarm_name          = "${var.name_prefix}-connect-queue-wait"
  alarm_description   = "Connect queue wait > 120 seconds"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "LongestQueueWaitTime"
  namespace           = "AWS/Connect"
  period              = 60
  statistic           = "Maximum"
  threshold           = 120
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = var.connect_instance_id
    MetricGroup = "Queue"
  }

  alarm_actions = [var.alert_topic_arn]
  tags          = { Name = "${var.name_prefix}-connect-queue-wait" }
}

# ── SQS Callback DLQ Alarm ────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "callback_queue_depth" {
  alarm_name          = "${var.name_prefix}-callback-queue-depth"
  alarm_description   = "Callback queue has > 50 unprocessed messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 50
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.callback_queue_name
  }

  alarm_actions = [var.alert_topic_arn]
  tags          = { Name = "${var.name_prefix}-callback-queue-depth" }
}

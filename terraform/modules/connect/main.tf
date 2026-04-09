# terraform/modules/connect/main.tf

resource "aws_connect_instance" "this" {
  identity_management_type = "CONNECT_MANAGED"
  inbound_calls_enabled    = true
  outbound_calls_enabled   = true
  instance_alias           = "${var.name_prefix}-connect"

  tags = {
    Name = "${var.name_prefix}-connect"
  }
}

# ── Storage Config: Recordings → S3 ───────────────────────────
resource "aws_connect_instance_storage_config" "recordings" {
  instance_id   = aws_connect_instance.this.id
  resource_type = "CALL_RECORDINGS"

  storage_config {
    s3_config {
      bucket_name   = var.recordings_bucket
      bucket_prefix = "connect-recordings"
    }
    storage_type = "S3"
  }
}

# ── Storage Config: Chat Transcripts → S3 ─────────────────────
resource "aws_connect_instance_storage_config" "transcripts" {
  instance_id   = aws_connect_instance.this.id
  resource_type = "CHAT_TRANSCRIPTS"

  storage_config {
    s3_config {
      bucket_name   = var.recordings_bucket
      bucket_prefix = "chat-transcripts"
    }
    storage_type = "S3"
  }
}

# ── Lambda Associations ───────────────────────────────────────
resource "aws_connect_lambda_function_association" "ivr_handler" {
  function_arn = var.ivr_handler_arn
  instance_id  = aws_connect_instance.this.id
}

resource "aws_connect_lambda_function_association" "menu_router" {
  function_arn = var.menu_router_arn
  instance_id  = aws_connect_instance.this.id
}

resource "aws_connect_lambda_function_association" "crm_lookup" {
  function_arn = var.crm_lookup_arn
  instance_id  = aws_connect_instance.this.id
}

resource "aws_connect_lambda_function_association" "callback_scheduler" {
  function_arn = var.callback_scheduler_arn
  instance_id  = aws_connect_instance.this.id
}

# ── Queue: Main IVR Queue ─────────────────────────────────────
resource "aws_connect_queue" "main_ivr" {
  instance_id           = aws_connect_instance.this.id
  name                  = "${var.name_prefix}-main-ivr-queue"
  description           = "Main IVR routing queue"
  hours_of_operation_id = aws_connect_hours_of_operation.twenty_four_seven.hours_of_operation_id

  tags = {
    Name = "${var.name_prefix}-main-ivr-queue"
  }
}

resource "aws_connect_queue" "callback" {
  instance_id           = aws_connect_instance.this.id
  name                  = "${var.name_prefix}-callback-queue"
  description           = "Callback scheduling queue"
  hours_of_operation_id = aws_connect_hours_of_operation.twenty_four_seven.hours_of_operation_id

  tags = {
    Name = "${var.name_prefix}-callback-queue"
  }
}

# ── Hours of Operation ────────────────────────────────────────
resource "aws_connect_hours_of_operation" "twenty_four_seven" {
  instance_id = aws_connect_instance.this.id
  name        = "${var.name_prefix}-24x7"
  description = "24/7 operation hours"
  time_zone   = "Asia/Calcutta"

  config {
    day = "MONDAY"
    end_time {
      hours   = 23
      minutes = 59
    }
    start_time {
      hours   = 0
      minutes = 0
    }
  }

  dynamic "config" {
    for_each = ["TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    content {
      day = config.value
      end_time {
        hours   = 23
        minutes = 59
      }
      start_time {
        hours   = 0
        minutes = 0
      }
    }
  }

  tags = {
    Name = "${var.name_prefix}-24x7"
  }
}

# ── Routing Profile ───────────────────────────────────────────
resource "aws_connect_routing_profile" "default" {
  instance_id               = aws_connect_instance.this.id
  name                      = "${var.name_prefix}-default-routing"
  description               = "Default IVR routing profile"
  default_outbound_queue_id = aws_connect_queue.main_ivr.queue_id

  media_concurrencies {
    channel     = "VOICE"
    concurrency = 1
  }

  queue_configs {
    channel  = "VOICE"
    delay    = 0
    priority = 1
    queue_id = aws_connect_queue.main_ivr.queue_id
  }

  tags = {
    Name = "${var.name_prefix}-default-routing"
  }
}

# ── Contact Flow: Main IVR ────────────────────────────────────
resource "aws_connect_contact_flow" "main_ivr" {
  instance_id = aws_connect_instance.this.id
  name        = "${var.name_prefix}-main-ivr-flow"
  description = "Main IVR contact flow with DTMF menu"
  type        = "CONTACT_FLOW"
  content     = file("${path.module}/../../../contact-flows/main-ivr-flow.json")

  tags = {
    Name = "${var.name_prefix}-main-ivr-flow"
  }
}

resource "aws_connect_contact_flow" "callback_flow" {
  instance_id = aws_connect_instance.this.id
  name        = "${var.name_prefix}-callback-flow"
  description = "Callback scheduling contact flow"
  type        = "CONTACT_FLOW"
  content     = file("${path.module}/../../../contact-flows/callback-flow.json")

  tags = {
    Name = "${var.name_prefix}-callback-flow"
  }
}

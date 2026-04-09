# terraform/modules/dynamodb/main.tf

# ── CallerProfiles ────────────────────────────────────────────
resource "aws_dynamodb_table" "caller_profiles" {
  name         = "${var.name_prefix}-CallerProfiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PhoneNumber"

  attribute {
    name = "PhoneNumber"
    type = "S"
  }

  attribute {
    name = "CustomerId"
    type = "S"
  }

  global_secondary_index {
    name            = "CustomerIdIndex"
    hash_key        = "CustomerId"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }

  tags = { Name = "${var.name_prefix}-CallerProfiles" }
}

# ── MenuConfig ────────────────────────────────────────────────
resource "aws_dynamodb_table" "menu_config" {
  name         = "${var.name_prefix}-MenuConfig"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "MenuId"
  range_key    = "Version"

  attribute {
    name = "MenuId"
    type = "S"
  }

  attribute {
    name = "Version"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = { Name = "${var.name_prefix}-MenuConfig" }
}

# ── CallLogs ──────────────────────────────────────────────────
resource "aws_dynamodb_table" "call_logs" {
  name         = "${var.name_prefix}-CallLogs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ContactId"
  range_key    = "Timestamp"

  attribute {
    name = "ContactId"
    type = "S"
  }

  attribute {
    name = "Timestamp"
    type = "S"
  }

  attribute {
    name = "PhoneNumber"
    type = "S"
  }

  global_secondary_index {
    name            = "PhoneNumberIndex"
    hash_key        = "PhoneNumber"
    range_key       = "Timestamp"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = { Name = "${var.name_prefix}-CallLogs" }
}

# ── Seed MenuConfig with default menu ─────────────────────────
resource "aws_dynamodb_table_item" "default_menu" {
  table_name = aws_dynamodb_table.menu_config.name
  hash_key   = aws_dynamodb_table.menu_config.hash_key
  range_key  = aws_dynamodb_table.menu_config.range_key

  item = jsonencode({
    MenuId  = { S = "MAIN_MENU" }
    Version = { S = "v1" }
    Active  = { BOOL = true }
    Options = {
      M = {
        "1" = { S = "BILLING" }
        "2" = { S = "SUPPORT" }
        "3" = { S = "SALES" }
        "0" = { S = "OPERATOR" }
        "9" = { S = "CALLBACK" }
      }
    }
    PromptKey = { S = "prompts/main-menu.mp3" }
    MaxRetries = { N = "3" }
    Timeout    = { N = "10" }
  })
}

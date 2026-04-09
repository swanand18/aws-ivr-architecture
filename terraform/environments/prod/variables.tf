# terraform/environments/prod/variables.tf

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "project" {
  description = "Project name used in resource naming"
  type        = string
  default     = "ivr"
}

variable "alert_email" {
  description = "Email for CloudWatch alarm notifications"
  type        = string
}

variable "connect_inbound_number" {
  description = "Phone number to claim in Amazon Connect (E.164 format)"
  type        = string
  default     = ""
}

variable "crm_api_endpoint" {
  description = "CRM REST API endpoint for caller profile lookups"
  type        = string
  default     = ""
  sensitive   = true
}

variable "lambda_log_level" {
  description = "Log level for Lambda functions"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.lambda_log_level)
    error_message = "Must be DEBUG, INFO, WARNING, or ERROR."
  }
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "enable_connect_recording" {
  description = "Enable call recording in Amazon Connect"
  type        = bool
  default     = true
}

variable "callback_retention_days" {
  description = "SQS message retention in seconds for callback queue"
  type        = number
  default     = 86400 # 24 hours
}

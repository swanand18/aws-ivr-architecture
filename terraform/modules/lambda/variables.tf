# terraform/modules/lambda/variables.tf
variable "name_prefix"            { type = string }
variable "environment"            { type = string }
variable "region"                 { type = string }
variable "account_id"             { type = string }
variable "caller_profiles_table"  { type = string }
variable "menu_config_table"      { type = string }
variable "call_logs_table"        { type = string }
variable "audio_bucket"           { type = string }
variable "recordings_bucket"      { type = string }
variable "callback_queue_url"     { type = string }
variable "alert_topic_arn"        { type = string }
variable "kms_key_arn"            { type = string }

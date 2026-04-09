# variables.tf
variable "name_prefix"           { type = string }
variable "environment"           { type = string }
variable "region"                { type = string }
variable "lambda_function_names" { type = map(string) }
variable "connect_instance_id"   { type = string }
variable "callback_queue_name"   { type = string }
variable "alert_topic_arn"       { type = string }

# terraform/modules/connect/variables.tf
variable "name_prefix" { type = string }
variable "environment" { type = string }
variable "region"      { type = string }
variable "ivr_handler_arn" { type = string }
variable "menu_router_arn" { type = string }
variable "crm_lookup_arn" { type = string }
variable "callback_scheduler_arn" { type = string }
variable "recordings_bucket" { type = string }
variable "audio_bucket" { type = string }

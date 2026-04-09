# variables.tf
variable "name_prefix"                      { type = string }
variable "environment"                      { type = string }
variable "kms_key_arn"                      { type = string }
variable "recording_processor_arn"          { type = string; default = "" }
variable "recording_processor_permission_id"{ type = string; default = "" }

# outputs.tf

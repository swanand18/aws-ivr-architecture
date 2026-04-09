# variables.tf
variable "name_prefix"          { type = string }
variable "environment"          { type = string }
variable "region"               { type = string }
variable "crm_lookup_arn"       { type = string }
variable "crm_lookup_invoke_arn"{ type = string }

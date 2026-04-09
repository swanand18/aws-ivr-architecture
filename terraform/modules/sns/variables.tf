# variables.tf
variable "name_prefix"  { type = string }
variable "environment"  { type = string }
variable "alert_email"  { type = string; default = "" }

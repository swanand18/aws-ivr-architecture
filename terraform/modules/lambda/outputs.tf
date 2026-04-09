# terraform/modules/lambda/outputs.tf

output "ivr_handler_arn"          { value = aws_lambda_function.this["ivr-handler"].arn }
output "menu_router_arn"          { value = aws_lambda_function.this["menu-router"].arn }
output "crm_lookup_arn"           { value = aws_lambda_function.this["crm-lookup"].arn }
output "crm_lookup_invoke_arn"    { value = aws_lambda_function.this["crm-lookup"].invoke_arn }
output "callback_scheduler_arn"   { value = aws_lambda_function.this["callback-scheduler"].arn }
output "recording_processor_arn"  { value = aws_lambda_function.this["recording-processor"].arn }

output "all_function_names" {
  value = { for k, v in aws_lambda_function.this : k => v.function_name }
}

output "function_arns" {
  value = { for k, v in aws_lambda_function.this : k => v.arn }
}

# terraform/environments/prod/outputs.tf

output "connect_instance_id" {
  description = "Amazon Connect instance ID"
  value       = module.connect.instance_id
}

output "connect_instance_arn" {
  description = "Amazon Connect instance ARN"
  value       = module.connect.instance_arn
}

output "connect_inbound_number" {
  description = "Claimed inbound phone number"
  value       = module.connect.claimed_number
}

output "api_gateway_invoke_url" {
  description = "API Gateway invoke URL for CRM webhook"
  value       = module.api_gateway.invoke_url
}

output "callback_queue_url" {
  description = "SQS Callback Queue URL"
  value       = module.sqs.callback_queue_url
}

output "audio_prompts_bucket" {
  description = "S3 bucket for IVR audio prompts"
  value       = module.s3.audio_prompts_bucket_name
}

output "recordings_bucket" {
  description = "S3 bucket for call recordings"
  value       = module.s3.recordings_bucket_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${module.monitoring.dashboard_name}"
}

output "lambda_function_arns" {
  description = "Map of Lambda function ARNs"
  value       = module.lambda.function_arns
}

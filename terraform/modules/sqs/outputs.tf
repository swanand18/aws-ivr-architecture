# terraform/modules/sqs/outputs.tf
output "callback_queue_url"  { value = aws_sqs_queue.callback.url }
output "callback_queue_arn"  { value = aws_sqs_queue.callback.arn }
output "callback_queue_name" { value = aws_sqs_queue.callback.name }
output "callback_dlq_arn"    { value = aws_sqs_queue.callback_dlq.arn }

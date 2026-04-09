# terraform/modules/connect/outputs.tf
output "instance_id"  { value = aws_connect_instance.this.id }
output "instance_arn" { value = aws_connect_instance.this.arn }
output "claimed_number" {
  value = try(aws_connect_phone_number.inbound[0].phone_number, "not-claimed")
}
output "main_queue_id"     { value = aws_connect_queue.main_ivr.queue_id }
output "callback_queue_id" { value = aws_connect_queue.callback.queue_id }
output "main_flow_id"      { value = aws_connect_contact_flow.main_ivr.contact_flow_id }

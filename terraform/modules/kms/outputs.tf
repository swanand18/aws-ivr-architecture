output "key_arn"   { value = aws_kms_key.ivr.arn }
output "key_id"    { value = aws_kms_key.ivr.key_id }
output "key_alias" { value = aws_kms_alias.ivr.name }

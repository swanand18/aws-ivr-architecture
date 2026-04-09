# outputs.tf
output "caller_profiles_table_name" { value = aws_dynamodb_table.caller_profiles.name }
output "menu_config_table_name"     { value = aws_dynamodb_table.menu_config.name }
output "call_logs_table_name"       { value = aws_dynamodb_table.call_logs.name }
output "caller_profiles_table_arn"  { value = aws_dynamodb_table.caller_profiles.arn }
output "menu_config_table_arn"      { value = aws_dynamodb_table.menu_config.arn }
output "call_logs_table_arn"        { value = aws_dynamodb_table.call_logs.arn }

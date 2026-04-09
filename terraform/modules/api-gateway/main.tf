# terraform/modules/api-gateway/main.tf
# REST API for external CRM webhook → crm-lookup Lambda

resource "aws_api_gateway_rest_api" "ivr" {
  name        = "${var.name_prefix}-ivr-api"
  description = "IVR platform CRM webhook API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = { Name = "${var.name_prefix}-ivr-api" }
}

resource "aws_api_gateway_resource" "caller" {
  rest_api_id = aws_api_gateway_rest_api.ivr.id
  parent_id   = aws_api_gateway_rest_api.ivr.root_resource_id
  path_part   = "caller"
}

resource "aws_api_gateway_method" "get_caller" {
  rest_api_id      = aws_api_gateway_rest_api.ivr.id
  resource_id      = aws_api_gateway_resource.caller.id
  http_method      = "GET"
  authorization    = "AWS_IAM"
  api_key_required = false
}

resource "aws_api_gateway_integration" "crm_lookup" {
  rest_api_id             = aws_api_gateway_rest_api.ivr.id
  resource_id             = aws_api_gateway_resource.caller.id
  http_method             = aws_api_gateway_method.get_caller.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.crm_lookup_invoke_arn
}

resource "aws_api_gateway_deployment" "prod" {
  rest_api_id = aws_api_gateway_rest_api.ivr.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.caller,
      aws_api_gateway_method.get_caller,
      aws_api_gateway_integration.crm_lookup,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.prod.id
  rest_api_id   = aws_api_gateway_rest_api.ivr.id
  stage_name    = var.environment

  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn
  }
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name              = "/aws/apigateway/${var.name_prefix}-ivr-api"
  retention_in_days = 30
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.crm_lookup_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.ivr.execution_arn}/*/*"
}

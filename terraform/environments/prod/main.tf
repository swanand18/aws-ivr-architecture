# terraform/environments/prod/main.tf

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  backend "s3" {
    bucket         = "swanand-eks-terraform-state"
    key            = "ivr/prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-ivr-architecture"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "swanand.awatade@gmail.com"
      CostCenter  = "IVR-Platform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  name_prefix = "${var.project}-${var.environment}"
}

# ── S3 Module ─────────────────────────────────────────────────
module "s3" {
  source      = "../../modules/s3"
  name_prefix = local.name_prefix
  environment = var.environment
  kms_key_arn = module.kms.key_arn
}

# ── DynamoDB Module ───────────────────────────────────────────
module "dynamodb" {
  source      = "../../modules/dynamodb"
  name_prefix = local.name_prefix
  environment = var.environment
  kms_key_arn = module.kms.key_arn
}

# ── Lambda Module ─────────────────────────────────────────────
module "lambda" {
  source      = "../../modules/lambda"
  name_prefix = local.name_prefix
  environment = var.environment
  region      = local.region
  account_id  = local.account_id

  caller_profiles_table = module.dynamodb.caller_profiles_table_name
  menu_config_table     = module.dynamodb.menu_config_table_name
  call_logs_table       = module.dynamodb.call_logs_table_name
  audio_bucket          = module.s3.audio_prompts_bucket_name
  recordings_bucket     = module.s3.recordings_bucket_name
  callback_queue_url    = module.sqs.callback_queue_url
  alert_topic_arn       = module.sns.alert_topic_arn
  kms_key_arn           = module.kms.key_arn
}

# ── Amazon Connect Module ─────────────────────────────────────
module "connect" {
  source      = "../../modules/connect"
  name_prefix = local.name_prefix
  environment = var.environment
  region      = local.region

  ivr_handler_arn       = module.lambda.ivr_handler_arn
  menu_router_arn       = module.lambda.menu_router_arn
  crm_lookup_arn        = module.lambda.crm_lookup_arn
  callback_scheduler_arn = module.lambda.callback_scheduler_arn
  recordings_bucket     = module.s3.recordings_bucket_name
  audio_bucket          = module.s3.audio_prompts_bucket_name
}

# ── API Gateway Module ────────────────────────────────────────
module "api_gateway" {
  source      = "../../modules/api-gateway"
  name_prefix = local.name_prefix
  environment = var.environment
  region      = local.region

  crm_lookup_arn        = module.lambda.crm_lookup_arn
  crm_lookup_invoke_arn = module.lambda.crm_lookup_invoke_arn
}

# ── SQS ───────────────────────────────────────────────────────
module "sqs" {
  source      = "../../modules/sqs"
  name_prefix = local.name_prefix
  environment = var.environment
  kms_key_arn = module.kms.key_arn
}

# ── SNS ───────────────────────────────────────────────────────
module "sns" {
  source         = "../../modules/sns"
  name_prefix    = local.name_prefix
  environment    = var.environment
  alert_email    = var.alert_email
}

# ── KMS ───────────────────────────────────────────────────────
module "kms" {
  source      = "../../modules/kms"
  name_prefix = local.name_prefix
  environment = var.environment
  account_id  = local.account_id
}

# ── CloudWatch Dashboards & Alarms ────────────────────────────
module "monitoring" {
  source      = "../../modules/monitoring"
  name_prefix = local.name_prefix
  environment = var.environment
  region      = local.region

  lambda_function_names = module.lambda.all_function_names
  connect_instance_id   = module.connect.instance_id
  callback_queue_name   = module.sqs.callback_queue_name
  alert_topic_arn       = module.sns.alert_topic_arn
}

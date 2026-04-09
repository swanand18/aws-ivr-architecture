#!/usr/bin/env bash
# scripts/bootstrap-backend.sh
# Creates the S3 + DynamoDB Terraform backend (idempotent)
set -euo pipefail

BUCKET="swanand-eks-terraform-state"
TABLE="terraform-lock"
REGION="${AWS_REGION:-ap-south-1}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Bootstrapping Terraform backend"
echo "  Bucket : $BUCKET"
echo "  Table  : $TABLE"
echo "  Region : $REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── S3 Bucket ────────────────────────────────────────────────
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "✓  S3 bucket already exists: $BUCKET"
else
  echo "→  Creating S3 bucket: $BUCKET"
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket \
      --bucket "$BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi

  aws s3api put-bucket-versioning \
    --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled

  aws s3api put-bucket-encryption \
    --bucket "$BUCKET" \
    --server-side-encryption-configuration '{
      "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
    }'

  aws s3api put-public-access-block \
    --bucket "$BUCKET" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  echo "✓  S3 bucket created and secured"
fi

# ── DynamoDB Lock Table ───────────────────────────────────────
if aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" 2>/dev/null; then
  echo "✓  DynamoDB table already exists: $TABLE"
else
  echo "→  Creating DynamoDB lock table: $TABLE"
  aws dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION"

  aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"
  echo "✓  DynamoDB lock table created"
fi

echo ""
echo "✅  Terraform backend ready"
echo ""
echo "Next step:"
echo "  cd terraform/environments/prod"
echo "  cp terraform.tfvars.example terraform.tfvars"
echo "  # edit terraform.tfvars"
echo "  terraform init"

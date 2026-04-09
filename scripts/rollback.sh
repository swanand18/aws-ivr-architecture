#!/usr/bin/env bash
# scripts/rollback.sh <environment> <lambda-function> <version>
# Rolls back a specific Lambda function to a previous published version.
# Usage: bash scripts/rollback.sh prod ivr-handler 5
set -euo pipefail

ENV="${1:-prod}"
FN_SHORT="${2:-}"
VERSION="${3:-}"
REGION="${AWS_REGION:-ap-south-1}"

if [ -z "$FN_SHORT" ] || [ -z "$VERSION" ]; then
  echo "Usage: $0 <environment> <function-name> <version>"
  echo "  e.g: $0 prod ivr-handler 5"
  exit 1
fi

FUNCTION_NAME="ivr-${ENV}-${FN_SHORT}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Rolling back Lambda"
echo "  Function : $FUNCTION_NAME"
echo "  Version  : $VERSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check version exists
aws lambda get-function \
  --function-name "${FUNCTION_NAME}:${VERSION}" \
  --region "$REGION" \
  --query 'Configuration.Version' \
  --output text > /dev/null

# Update alias 'live' to point to previous version
aws lambda update-alias \
  --function-name "$FUNCTION_NAME" \
  --name live \
  --function-version "$VERSION" \
  --region "$REGION"

echo "✅  $FUNCTION_NAME rolled back to version $VERSION"

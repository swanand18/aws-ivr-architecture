#!/usr/bin/env bash
# scripts/deploy-lambdas.sh <environment>
# Packages and deploys all Lambda functions independently.
# Usage: bash scripts/deploy-lambdas.sh prod
set -euo pipefail

ENV="${1:-prod}"
REGION="${AWS_REGION:-ap-south-1}"
PREFIX="ivr-${ENV}"
DIST_DIR="lambda/.dist"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

FUNCTIONS=(ivr-handler menu-router crm-lookup callback-scheduler recording-processor)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploying Lambda functions"
echo "  Environment : $ENV"
echo "  Prefix      : $PREFIX"
echo "  Region      : $REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "$ROOT_DIR/$DIST_DIR"

for FN in "${FUNCTIONS[@]}"; do
  echo ""
  echo "→  Packaging: $FN"

  SRC="$ROOT_DIR/lambda/$FN"
  ZIP="$ROOT_DIR/$DIST_DIR/${FN}.zip"

  # Install dependencies into a tmp package dir
  TMP="$(mktemp -d)"
  cp -r "$SRC/"* "$TMP/"

  if [ -f "$SRC/requirements.txt" ]; then
    pip install -q -r "$SRC/requirements.txt" -t "$TMP/" --upgrade
  fi

  # Package zip
  (cd "$TMP" && zip -qr "$ZIP" .)
  rm -rf "$TMP"

  FUNCTION_NAME="${PREFIX}-${FN}"

  # Update function code
  echo "   Updating: $FUNCTION_NAME"
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP" \
    --region "$REGION" \
    --output table \
    --query 'FunctionName' 2>&1 | tail -1

  # Wait for update to complete
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

  # Publish a new version
  VERSION=$(aws lambda publish-version \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Version' \
    --output text)

  echo "   ✓  $FUNCTION_NAME → version $VERSION"
done

echo ""
echo "✅  All Lambda functions deployed successfully"

#!/usr/bin/env bash
# scripts/import-contact-flows.sh <environment>
# Imports / updates Amazon Connect contact flows from JSON definitions.
# Usage: bash scripts/import-contact-flows.sh prod
set -euo pipefail

ENV="${1:-prod}"
REGION="${AWS_REGION:-ap-south-1}"
PREFIX="ivr-${ENV}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLOWS_DIR="$ROOT_DIR/contact-flows"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Importing Contact Flows"
echo "  Environment : $ENV"
echo "  Region      : $REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Discover Connect instance ─────────────────────────────────
INSTANCE_ID="${CONNECT_INSTANCE_ID:-}"

if [ -z "$INSTANCE_ID" ]; then
  echo "→  Looking up Connect instance: $PREFIX-connect"
  INSTANCE_ID=$(aws connect list-instances \
    --region "$REGION" \
    --query "InstanceSummaryList[?InstanceAlias=='${PREFIX}-connect'].Id" \
    --output text)
fi

if [ -z "$INSTANCE_ID" ]; then
  echo "✗  Could not find Connect instance with alias '${PREFIX}-connect'"
  echo "   Set CONNECT_INSTANCE_ID env var or deploy infrastructure first."
  exit 1
fi

echo "   Instance ID: $INSTANCE_ID"

# ── Helper: get existing flow ID by name ─────────────────────
get_flow_id() {
  local name="$1"
  aws connect list-contact-flows \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query "ContactFlowSummaryList[?Name=='${name}'].Id" \
    --output text
}

# ── Import each flow ──────────────────────────────────────────
FLOW_MAP=(
  "main-ivr-flow.json:${PREFIX}-main-ivr-flow"
  "callback-flow.json:${PREFIX}-callback-flow"
)

for ENTRY in "${FLOW_MAP[@]}"; do
  FILE="${ENTRY%%:*}"
  FLOW_NAME="${ENTRY##*:}"
  FLOW_PATH="$FLOWS_DIR/$FILE"

  if [ ! -f "$FLOW_PATH" ]; then
    echo "✗  Flow file not found: $FLOW_PATH"
    continue
  fi

  echo ""
  echo "→  Processing: $FLOW_NAME"

  EXISTING_ID=$(get_flow_id "$FLOW_NAME")
  CONTENT=$(cat "$FLOW_PATH")

  if [ -n "$EXISTING_ID" ]; then
    echo "   Updating existing flow: $EXISTING_ID"
    aws connect update-contact-flow-content \
      --instance-id "$INSTANCE_ID" \
      --contact-flow-id "$EXISTING_ID" \
      --content "$CONTENT" \
      --region "$REGION"
    echo "   ✓  Updated $FLOW_NAME"
  else
    echo "   Creating new flow"
    NEW_ID=$(aws connect create-contact-flow \
      --instance-id "$INSTANCE_ID" \
      --name "$FLOW_NAME" \
      --type CONTACT_FLOW \
      --content "$CONTENT" \
      --region "$REGION" \
      --query 'ContactFlowId' \
      --output text)
    echo "   ✓  Created $FLOW_NAME → $NEW_ID"
  fi
done

echo ""
echo "✅  Contact flows imported successfully"

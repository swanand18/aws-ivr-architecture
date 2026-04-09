#!/usr/bin/env bash
# scripts/seed-dynamodb.sh <environment>
# Seeds DynamoDB tables with default data.
# Usage: bash scripts/seed-dynamodb.sh prod
set -euo pipefail

ENV="${1:-prod}"
REGION="${AWS_REGION:-ap-south-1}"
PREFIX="ivr-${ENV}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Seeding DynamoDB tables"
echo "  Environment : $ENV  |  Region : $REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── MenuConfig: MAIN_MENU ─────────────────────────────────────
echo "→  Seeding MenuConfig: MAIN_MENU"
aws dynamodb put-item \
  --table-name "${PREFIX}-MenuConfig" \
  --region "$REGION" \
  --item '{
    "MenuId":     {"S": "MAIN_MENU"},
    "Version":    {"S": "v1"},
    "Active":     {"BOOL": true},
    "Options": {"M": {
      "1": {"S": "BILLING"},
      "2": {"S": "SUPPORT"},
      "3": {"S": "SALES"},
      "0": {"S": "OPERATOR"},
      "9": {"S": "CALLBACK"}
    }},
    "PromptKey":   {"S": "prompts/main-menu.mp3"},
    "MaxRetries":  {"N": "3"},
    "Timeout":     {"N": "10"}
  }'
echo "   ✓  MAIN_MENU seeded"

# ── MenuConfig: BILLING_MENU ──────────────────────────────────
echo "→  Seeding MenuConfig: BILLING_MENU"
aws dynamodb put-item \
  --table-name "${PREFIX}-MenuConfig" \
  --region "$REGION" \
  --item '{
    "MenuId":     {"S": "BILLING_MENU"},
    "Version":    {"S": "v1"},
    "Active":     {"BOOL": true},
    "Options": {"M": {
      "1": {"S": "PAYMENT"},
      "2": {"S": "INVOICE"},
      "3": {"S": "REFUND"},
      "0": {"S": "OPERATOR"},
      "9": {"S": "CALLBACK"},
      "*": {"S": "MAIN_MENU"}
    }},
    "PromptKey":  {"S": "prompts/billing-menu.mp3"},
    "MaxRetries": {"N": "3"},
    "Timeout":    {"N": "10"}
  }'
echo "   ✓  BILLING_MENU seeded"

# ── CallerProfiles: sample VIP entry ─────────────────────────
echo "→  Seeding CallerProfiles: sample VIP"
aws dynamodb put-item \
  --table-name "${PREFIX}-CallerProfiles" \
  --region "$REGION" \
  --item '{
    "PhoneNumber":       {"S": "+910000000001"},
    "CustomerId":        {"S": "DEMO-VIP-001"},
    "Name":              {"S": "Demo VIP Customer"},
    "AccountStatus":     {"S": "ACTIVE"},
    "VIP":               {"BOOL": true},
    "PreferredLanguage": {"S": "en-IN"},
    "PreferredQueue":    {"S": "VIPQueue"},
    "LastCallDate":      {"S": "2024-04-01"}
  }'
echo "   ✓  Demo VIP profile seeded"

echo ""
echo "✅  DynamoDB seeding complete"
echo ""
echo "Verify with:"
echo "  aws dynamodb scan --table-name ${PREFIX}-MenuConfig --region $REGION | jq '.Count'"

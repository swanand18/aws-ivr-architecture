# 🚀 Deployment Guide — AWS IVR Architecture

End-to-end instructions to go from zero to a live Amazon Connect IVR in `ap-south-1`.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| AWS CLI | ≥ 2.x | `curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o a.zip && unzip a.zip && sudo ./aws/install` |
| Terraform | ≥ 1.7 | `https://developer.hashicorp.com/terraform/install` |
| Python | ≥ 3.12 | `sudo apt install python3.12` |
| jq | any | `sudo apt install jq` |

Configure AWS credentials with AdministratorAccess (for initial deploy):

```bash
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region: ap-south-1
# Default output format: json
```

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/swanand18/aws-ivr-architecture.git
cd aws-ivr-architecture
```

---

## Step 2 — Bootstrap Terraform Backend

This creates the S3 state bucket and DynamoDB lock table (reuses existing
`swanand-eks-terraform-state` if already present from other portfolio repos).

```bash
bash scripts/bootstrap-backend.sh
```

Expected output:
```
✓  S3 bucket already exists: swanand-eks-terraform-state
✓  DynamoDB lock table already exists: terraform-lock
✅  Terraform backend ready
```

---

## Step 3 — Configure Variables

```bash
cp terraform/environments/prod/terraform.tfvars.example \
   terraform/environments/prod/terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region             = "ap-south-1"
environment            = "prod"
project                = "ivr"
alert_email            = "swanand.awatade@gmail.com"   # ← your email
connect_inbound_number = "+911234567890"                # ← leave empty to skip claiming
crm_api_endpoint       = ""                             # ← optional external CRM
```

---

## Step 4 — Deploy Infrastructure

```bash
cd terraform/environments/prod

terraform init
terraform validate
terraform plan -out=tfplan

# Review plan output, then apply
terraform apply tfplan
```

This creates:
- Amazon Connect instance (`ivr-prod-connect`)
- 5 Lambda functions with least-privilege IAM roles
- DynamoDB tables (CallerProfiles, MenuConfig, CallLogs)
- S3 buckets (audio-prompts, recordings) with KMS encryption
- SQS callback queue + DLQ
- SNS alert topic
- API Gateway REST endpoint
- CloudWatch dashboard + alarms
- KMS key for all encryption

Approximate time: **8–12 minutes**

---

## Step 5 — Seed DynamoDB Menu Config

The Terraform `aws_dynamodb_table_item` resource seeds the default menu,
but you can re-seed or add entries manually:

```bash
bash scripts/seed-dynamodb.sh prod
```

Or manually:

```bash
aws dynamodb put-item \
  --table-name ivr-prod-MenuConfig \
  --item '{
    "MenuId":   {"S": "MAIN_MENU"},
    "Version":  {"S": "v1"},
    "Active":   {"BOOL": true},
    "Options":  {"M": {
      "1": {"S": "BILLING"},
      "2": {"S": "SUPPORT"},
      "3": {"S": "SALES"},
      "0": {"S": "OPERATOR"},
      "9": {"S": "CALLBACK"}
    }},
    "MaxRetries": {"N": "3"}
  }' \
  --region ap-south-1
```

---

## Step 6 — Upload Audio Prompts

Upload your IVR audio prompts (MP3/WAV) to the audio-prompts S3 bucket:

```bash
BUCKET=$(terraform output -raw audio_prompts_bucket)

aws s3 cp prompts/greeting-new.mp3     s3://${BUCKET}/prompts/
aws s3 cp prompts/greeting-returning.mp3 s3://${BUCKET}/prompts/
aws s3 cp prompts/greeting-vip.mp3     s3://${BUCKET}/prompts/
aws s3 cp prompts/main-menu.mp3        s3://${BUCKET}/prompts/
aws s3 cp prompts/routing-billing.mp3  s3://${BUCKET}/prompts/
aws s3 cp prompts/routing-support.mp3  s3://${BUCKET}/prompts/
aws s3 cp prompts/routing-sales.mp3    s3://${BUCKET}/prompts/
aws s3 cp prompts/invalid-input.mp3    s3://${BUCKET}/prompts/
aws s3 cp prompts/timeout.mp3          s3://${BUCKET}/prompts/
aws s3 cp prompts/system-error.mp3     s3://${BUCKET}/prompts/
```

> **Tip:** Amazon Connect also supports Text-to-Speech (Polly) inline —
> you can skip audio uploads and use the TTS prompts in the contact flows directly.

---

## Step 7 — Import Contact Flows

```bash
INSTANCE_ID=$(terraform output -raw connect_instance_id)

CONNECT_INSTANCE_ID=$INSTANCE_ID \
  bash scripts/import-contact-flows.sh prod
```

---

## Step 8 — Run Smoke Tests

```bash
cd tests
pip install -r requirements.txt

python -m pytest integration/test_smoke.py \
  --env=prod \
  --region=ap-south-1 \
  -v
```

Expected: 6 tests pass ✅

---

## Step 9 — Claim a Phone Number (Optional)

In the AWS Console:
1. Navigate to **Amazon Connect → Phone numbers → Claim a number**
2. Select **DID (Direct Inward Dialing)** → India
3. Assign to the **Main IVR contact flow**

Or via CLI:
```bash
INSTANCE_ID=$(cd terraform/environments/prod && terraform output -raw connect_instance_id)

aws connect search-available-phone-numbers \
  --target-arn "arn:aws:connect:ap-south-1:$(aws sts get-caller-identity --query Account --output text):instance/${INSTANCE_ID}" \
  --phone-number-country-code IN \
  --phone-number-type DID \
  --region ap-south-1
```

---

## Step 10 — Set Up GitHub Actions CI/CD

### Create OIDC IAM Role for GitHub Actions

```bash
# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create OIDC provider (once per account)
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"

# Create trust policy
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:swanand18/aws-ivr-architecture:*"
      }
    }
  }]
}
EOF

# Create deploy role
aws iam create-role \
  --role-name ivr-github-actions-deploy \
  --assume-role-policy-document file:///tmp/trust-policy.json

aws iam attach-role-policy \
  --role-name ivr-github-actions-deploy \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

ROLE_ARN=$(aws iam get-role --role-name ivr-github-actions-deploy --query Role.Arn --output text)
echo "Add this to GitHub Secrets → AWS_DEPLOY_ROLE_ARN: $ROLE_ARN"
```

### GitHub Repository Secrets

Add these secrets at `https://github.com/swanand18/aws-ivr-architecture/settings/secrets/actions`:

| Secret | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN from above |
| `ALERT_EMAIL` | `swanand.awatade@gmail.com` |
| `CRM_API_ENDPOINT` | CRM URL or empty string |
| `CONNECT_INSTANCE_ID` | From `terraform output connect_instance_id` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook (optional) |

---

## Monitoring & Dashboards

After deployment, view the CloudWatch dashboard:

```bash
cd terraform/environments/prod
terraform output cloudwatch_dashboard_url
```

Key alarms configured:
- Lambda errors > 5 / 5 min → SNS email
- Lambda throttles > 0 → SNS email
- Connect queue wait > 120 sec → SNS email
- Callback queue depth > 50 → SNS email

---

## Teardown

```bash
cd terraform/environments/prod
terraform destroy \
  -var="alert_email=swanand.awatade@gmail.com" \
  -var="crm_api_endpoint="
```

> Note: Amazon Connect phone numbers must be released manually in the console before `destroy` will succeed.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Connect instance already exists` | Change `instance_alias` in Connect module or import existing instance |
| Lambda timeout in Connect flow | Increase Lambda `timeout` in `terraform/modules/lambda/main.tf` |
| DynamoDB `ResourceNotFoundException` | Run `terraform apply` again — table may still be creating |
| Contact flow import fails `InvalidContactFlowException` | Validate JSON at `contact-flows/*.json` — check Lambda ARNs are correct |
| S3 trigger not firing | Verify Lambda permission `aws_lambda_permission.s3_invoke_recording_processor` was applied |

# ☎️ AWS Cloud IVR Architecture

Production-grade Interactive Voice Response (IVR) system built on **Amazon Connect**, **Lambda**, **DynamoDB**, and **Terraform** — fully automated CI/CD via GitHub Actions.

---

## 🏗️ Architecture Overview

```
Caller
  │
  ▼
Amazon Connect (Inbound DID / TFN)
  │
  ├──► Contact Flow Engine
  │         │
  │         ├──► Lambda: ivr-handler        → Main menu routing
  │         ├──► Lambda: crm-lookup         → Caller identification (DynamoDB / API)
  │         ├──► Lambda: menu-router        → DTMF / Speech intent routing
  │         ├──► Lambda: callback-scheduler → Queue callback + SQS
  │         └──► Lambda: recording-processor→ Post-call S3 + transcription
  │
  ├──► DynamoDB
  │         ├── CallerProfiles table
  │         ├── MenuConfig table
  │         └── CallLogs table
  │
  ├──► S3
  │         ├── ivr-audio-prompts/
  │         └── ivr-recordings/
  │
  ├──► SQS  → Callback Queue
  ├──► SNS  → Alerts / Escalation
  └──► CloudWatch → Dashboards + Alarms
```

---

## 📦 Stack

| Layer | Service |
|---|---|
| Contact Center | Amazon Connect |
| Compute | AWS Lambda (Python 3.12) |
| Database | Amazon DynamoDB |
| Storage | Amazon S3 |
| Queuing | Amazon SQS |
| Notifications | Amazon SNS |
| Secrets | AWS Secrets Manager |
| IaC | Terraform 1.7+ |
| CI/CD | GitHub Actions |
| Monitoring | CloudWatch + Dashboards |
| Security | IAM least-privilege, KMS encryption |

---

## 🚀 Quick Start

### Prerequisites

```bash
# Required tools
terraform >= 1.7
aws-cli >= 2.x
python >= 3.12
jq
```

### 1. Clone & Configure

```bash
git clone https://github.com/swanand18/aws-ivr-architecture.git
cd aws-ivr-architecture

# Copy and edit variables
cp terraform/environments/prod/terraform.tfvars.example \
   terraform/environments/prod/terraform.tfvars
```

### 2. Bootstrap Terraform Backend

```bash
bash scripts/bootstrap-backend.sh
```

### 3. Deploy Infrastructure

```bash
cd terraform/environments/prod
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 4. Deploy Lambda Functions

```bash
bash scripts/deploy-lambdas.sh prod
```

### 5. Import Contact Flows

```bash
bash scripts/import-contact-flows.sh prod
```

---

## 📁 Repository Structure

```
aws-ivr-architecture/
├── terraform/
│   ├── modules/
│   │   ├── connect/          # Amazon Connect instance + flows
│   │   ├── lambda/           # Lambda functions + IAM
│   │   ├── dynamodb/         # Tables + autoscaling
│   │   ├── s3/               # Buckets + lifecycle
│   │   └── api-gateway/      # REST API for CRM webhook
│   └── environments/
│       └── prod/             # Root module + tfvars
├── lambda/
│   ├── ivr-handler/          # Main IVR entry point
│   ├── menu-router/          # DTMF/speech routing engine
│   ├── crm-lookup/           # Caller profile lookup
│   ├── callback-scheduler/   # Queue callback logic
│   └── recording-processor/  # Post-call processing
├── contact-flows/            # Amazon Connect flow JSONs
├── scripts/                  # Bootstrap, deploy, rollback
├── tests/                    # Unit + integration tests
└── .github/workflows/        # CI/CD pipelines
```

---

## 🔐 Security

- All S3 buckets: versioning + SSE-KMS + block public access
- DynamoDB: encryption at rest (KMS)
- Lambda: least-privilege IAM roles per function
- Connect recordings: server-side encrypted in S3
- Secrets Manager for API keys / CRM credentials

---

## 📊 Monitoring

| Metric | Alarm Threshold |
|---|---|
| Lambda errors | > 5 in 5 min |
| Connect queue wait time | > 120 sec |
| DynamoDB throttles | > 0 |
| SQS callback queue depth | > 50 |

---

## 🧪 Testing

```bash
# Unit tests
cd tests && pip install -r requirements.txt
pytest unit/ -v

# Integration (requires deployed stack)
pytest integration/ -v --env=prod
```

---

## 📝 Author

**Swanand Awatade** · Senior DevOps / Cloud Infrastructure Engineer  
📧 swanand.awatade@gmail.com · 🐙 [github.com/swanand18](https://github.com/swanand18)

---

## 📄 License

MIT

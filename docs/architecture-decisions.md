# Architecture Decision Records

## ADR-001: Amazon Connect as IVR Platform

**Status:** Accepted  
**Date:** 2024-04

### Context
Need a cloud-native IVR with no on-premises hardware, pay-per-use pricing, and native AWS integration.

### Decision
Use **Amazon Connect** as the managed contact centre layer. Connect handles telephony, contact flows, recording, and agent routing — eliminating the need to manage Asterisk/FreeSWITCH clusters.

### Consequences
- ✅ No phone server infrastructure to maintain  
- ✅ Native Lambda invocations within contact flows  
- ✅ Built-in call recording → S3  
- ⚠️ Connect pricing includes per-minute charges; monitor with CloudWatch

---

## ADR-002: Lambda per Function (Not Monolith)

**Status:** Accepted

### Decision
Each IVR function (ivr-handler, menu-router, crm-lookup, callback-scheduler, recording-processor) is a separate Lambda with its own IAM role.

### Consequences
- ✅ Least-privilege IAM per function  
- ✅ Independent deploy / rollback per function  
- ✅ Separate CloudWatch log groups for debugging  
- ⚠️ Cold starts possible; mitigated with Provisioned Concurrency if needed

---

## ADR-003: DynamoDB for State (Not RDS)

**Status:** Accepted

### Decision
DynamoDB for CallerProfiles, MenuConfig, and CallLogs instead of Aurora/RDS.

### Consequences
- ✅ No VPC complexity for Lambda  
- ✅ Single-digit ms latency for caller lookups  
- ✅ PAY_PER_REQUEST matches sporadic IVR traffic  
- ⚠️ No complex SQL queries — mitigated by GSIs on PhoneNumber

---

## ADR-004: SQS for Callback Queue

**Status:** Accepted

### Decision
Use SQS with a DLQ for callback scheduling instead of Step Functions.

### Consequences
- ✅ Simple, reliable queue with at-least-once delivery  
- ✅ DLQ captures failed callbacks for manual inspection  
- ✅ Built-in retry with backoff  
- ⚠️ No built-in scheduler (e.g., "call back at 3 PM") — future enhancement via EventBridge Scheduler

---

## ADR-005: Terraform over CDK/SAM

**Status:** Accepted

### Decision
Terraform for all IaC. Shared state backend reuses existing `swanand-eks-terraform-state` bucket.

### Consequences
- ✅ Consistent with existing portfolio repos  
- ✅ Modular structure allows reuse across environments  
- ✅ Mature provider for `aws_connect_*` resources  
- ⚠️ Amazon Connect Terraform support is still evolving; some resources may need `aws_connect_*` data sources for import

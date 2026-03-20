# Sample Cases

Synthetic but plausible financial operations cases for demonstrating CaseLedger. Each case is designed to trigger a specific outcome path.

## Expected outcomes

| Case ID | Issue Type | Expected Outcome | Why |
|---|---|---|---|
| CASE-2026-001 | Contestação cobrança | `suggested_response` | R$180, has documents, no risk flags |
| CASE-2026-002 | Contestação cobrança | `human_review` | R$2300 > threshold + fraud flag |
| CASE-2026-003 | Contestação cobrança | `blocked` | No documents attached |
| CASE-2026-004 | Aumento limite | `suggested_response` | R$5000, 2yr client, no flags |
| CASE-2026-005 | Aumento limite | `human_review` | Recent account flag |
| CASE-2026-006 | Aumento limite | `blocked` | Active delinquency flag |
| CASE-2026-007 | Onboarding KYC | `suggested_response` | Complete docs, no flags |
| CASE-2026-008 | Onboarding KYC | `human_review` | PEP (politically exposed person) |

## Why these cases

Each case demonstrates a different decision path through the policy engine. Together they show that the system does not just generate responses — it applies versioned policy rules, classifies risk, and determines whether automation can proceed, human review is required, or the case should be blocked entirely.

The cases are deliberately simple. Real financial operations involve more context (transaction history, credit scoring, regulatory lookups). The goal here is to demonstrate the control flow, not to simulate a bank.

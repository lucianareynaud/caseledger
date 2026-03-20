# CaseLedger

Policy-bounded decision traces for AI-assisted financial operations.

CaseLedger is a reference architecture for regulated financial workflows where LLM-generated responses need versioned policy enforcement, human-in-the-loop gating, cost attribution, and auditable decision trails. It is not a chatbot. It is a control plane for operational cases.

## The problem

In regulated finance, an AI-generated response is not enough. The organization needs to answer: which policy was applied? What context was used? Why did automation stop? Who reviewed? How much did it cost? Most AI demos answer none of these. CaseLedger answers all of them.

## Architecture

```
POST /cases/submit
  │
  ├── CaseEnvelope         structured business context
  │     case_id, issue_type, product_line, customer_tier,
  │     risk_flags, documents, valor_brl
  │
  ├── Policy Engine         versioned YAML rules
  │     load policy by issue_type
  │     evaluate rules in order → first match wins
  │     determine outcome: suggested | human_review | blocked
  │
  ├── LLM Call (if not blocked)
  │     prompt built from policy template + case context
  │     model tier selected by case risk + customer segment
  │     call via llmscope gateway (cost, latency, envelope)
  │
  └── CaseOutcome           full provenance
        status, response_text, decision_reason,
        policy_id, policy_version, snippets_used,
        model_selected, cost_usd, trace_id
```

## Three outcomes

Every case resolves to exactly one outcome:

| Outcome | When | What happens |
|---|---|---|
| `suggested_response` | High confidence, policy permits | Response ready to send |
| `human_review` | High value, ambiguity, risk flags | Response drafted, needs approval |
| `blocked` | Policy gap, low confidence, missing docs | Case escalated, no response |

This is the core differentiator. The system does not just generate a response — it decides what to do with the response based on versioned policy and case context.

## Sample cases

Eight synthetic financial cases covering three issue types:

| Case | Issue | Outcome | Trigger |
|---|---|---|---|
| CASE-001 | Contestação R$180 | suggested | Standard case, docs present |
| CASE-002 | Contestação R$2300 | human_review | Fraud flag + high value |
| CASE-003 | Tarifa indevida | blocked | No documents |
| CASE-004 | Aumento limite R$5k | suggested | Clean history |
| CASE-005 | Aumento R$15k | human_review | Recent account |
| CASE-006 | Aumento crédito | blocked | Active delinquency |
| CASE-007 | Onboarding KYC | suggested | Complete docs |
| CASE-008 | Onboarding Private | human_review | PEP identified |

See `cases/README.md` for details.

## Policy engine

Policies are versioned YAML files in `policies/`. Each policy defines ordered rules with conditions and outcomes:

```yaml
policy_id: "contestacao_cobranca"
version: "2.1"
rules:
  - name: "valor_alto_revisao"
    condition: "valor_brl > 500"
    outcome: "human_review"
    reason: "valor acima do threshold de automação"
  - name: "sem_documentacao"
    condition: "no_documents"
    outcome: "blocked"
    reason: "documentação insuficiente"
  - name: "resolucao_padrao"
    condition: "default"
    outcome: "suggested_response"
    reason: "dentro dos parâmetros de automação"
```

Rules are evaluated in order. First match wins. If no rule matches, the system defaults to `human_review` for safety. Policies are configuration, not code — changing a threshold or adding a rule is a YAML edit, not a deploy.

## How it connects to llmscope

CaseLedger uses [llmscope](https://github.com/lucianareynaud/llmscope) as the LLM gateway. When a case needs an LLM response, the resolver calls `llmscope.call_llm()`. LLMScope handles:

- Provider abstraction (OpenAI, Anthropic)
- Cost attribution per request
- Token counting and budget enforcement
- OTel span with full telemetry
- Envelope construction with provenance

CaseLedger adds the business layer: policy lookup, outcome classification, decision reason, and audit trail. The two projects are complementary — llmscope is infrastructure, CaseLedger is the application.

```
CaseLedger (business logic, policy, outcomes)
  └── llmscope (gateway, cost, telemetry, envelope)
        └── Provider (OpenAI, Anthropic)
```

## Setup

### Local development

```bash
python3 -m venv .venv && source .venv/bin/activate

# Install CaseLedger + llmscope from local sibling
pip3 install -e ../llmscope -e ".[dev]"
```

### Run tests

```bash
python3 -m pytest tests/ -q
```

### Run the API

```bash
uvicorn app.main:app --reload
```

### Submit sample cases

```bash
make demo
```

Or manually:

```bash
curl -s -X POST http://localhost:8000/cases/submit \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "CASE-2026-001",
    "issue_type": "contestacao_cobranca",
    "product_line": "cartao_credito",
    "customer_tier": "standard",
    "description": "Cobrança duplicada de R$180",
    "documents": ["fatura.pdf"],
    "valor_brl": 180.0
  }' | python3 -m json.tool
```

### Inspect a case

```bash
curl -s http://localhost:8000/cases/CASE-2026-001 | python3 -m json.tool
```

## Project structure

```
caseledger/
├── src/caseledger/
│   ├── case.py          ← CaseEnvelope (business context)
│   ├── outcomes.py      ← CaseOutcome + OutcomeStatus
│   ├── policy.py        ← Policy engine (YAML rules)
│   └── resolver.py      ← Orchestration: policy → LLM → outcome
├── policies/
│   ├── contestacao_cobranca.yaml
│   ├── aumento_limite.yaml
│   └── onboarding_kyc.yaml
├── cases/
│   └── sample_cases.jsonl
├── app/                 ← FastAPI reference endpoints
├── tests/
├── docker-compose.yml   ← app + Jaeger
├── Makefile
└── pyproject.toml
```

## Related projects

- [llmscope](https://github.com/lucianareynaud/llmscope) — Observable cost control for production LLMs. The gateway layer that CaseLedger uses for every LLM call.
- [llm-eval-gate](https://github.com/lucianareynaud/llm-eval-gate) — Evidence-based quality gate that reads llmscope telemetry to produce go/no-go deployment decisions.

## What this is not

Not a chatbot. Not a customer-facing product. Not a bank simulation. It is a reference architecture demonstrating how AI-assisted financial operations can be policy-bounded, cost-attributed, and auditable — with explicit decision points for when automation proceeds, when humans review, and when the system stops.

## Regulatory context

This architecture is designed to be compatible with the direction of regulatory frameworks for AI in financial services, including Brazil's LGPD, the pending PL 2338/2023 (algorithmic impact assessment and contestability), and ANPD's AI regulatory agenda. The system provides: decision logging, policy versioning, human oversight points, cost transparency, and contestability paths — capabilities that anticipate regulatory requirements without depending on specific legislation.

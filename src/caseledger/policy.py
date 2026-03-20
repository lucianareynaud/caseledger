"""Policy engine — loads versioned rules and applies them to cases.

Policies are YAML files in the policies/ directory. Each policy
defines rules for a specific issue_type. Rules are evaluated in
order; the first matching rule determines the outcome status.

This is intentionally NOT a rules engine framework. It is a
simple, inspectable, auditable decision tree. The complexity
lives in the policy YAML, not in the engine code.

Policy YAML shape:
    policy_id: "contestacao_cobranca"
    version: "2.1"
    rules:
      - name: "high_value_review"
        condition: "valor_brl > 500"
        outcome: "human_review"
        reason: "valor acima do threshold de automação"
      - name: "missing_docs_block"
        condition: "no_documents"
        outcome: "blocked"
        reason: "documentação insuficiente para resolução"
      - name: "default_suggest"
        condition: "default"
        outcome: "suggested_response"
        reason: "caso dentro dos parâmetros de automação"
    prompt_template: |
      Você é um assistente de operações financeiras.
      Contexto do caso: {description}
      Política aplicável: {policy_context}
      Responda de forma clara e objetiva.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from caseledger.case import CaseEnvelope
from caseledger.outcomes import OutcomeStatus


@dataclass(frozen=True)
class PolicyRule:
    """A single rule within a policy."""

    name: str
    condition: str
    outcome: OutcomeStatus
    reason: str


@dataclass(frozen=True)
class Policy:
    """A loaded, versioned policy for a specific issue type."""

    policy_id: str
    version: str
    rules: list[PolicyRule]
    prompt_template: str
    raw_yaml: dict[str, Any] = field(
        default_factory=dict, repr=False
    )


def load_policy(path: Path) -> Policy:
    """Load a policy from a YAML file.

    Args:
        path: Path to the YAML policy file.

    Returns:
        Parsed Policy with typed rules.

    Raises:
        FileNotFoundError: If the YAML file doesn't exist.
        KeyError: If required fields are missing.
    """
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    rules = []
    for r in raw.get("rules", []):
        rules.append(
            PolicyRule(
                name=r["name"],
                condition=r["condition"],
                outcome=OutcomeStatus(r["outcome"]),
                reason=r["reason"],
            )
        )

    return Policy(
        policy_id=raw["policy_id"],
        version=raw["version"],
        rules=rules,
        prompt_template=raw.get("prompt_template", ""),
        raw_yaml=raw,
    )


def load_policies_from_dir(
    directory: Path,
) -> dict[str, Policy]:
    """Load all YAML policies from a directory.

    Returns a dict keyed by policy_id.
    """
    policies: dict[str, Policy] = {}
    if not directory.exists():
        return policies
    for path in sorted(directory.glob("*.yaml")):
        policy = load_policy(path)
        policies[policy.policy_id] = policy
    return policies


def evaluate_policy(
    policy: Policy,
    case: CaseEnvelope,
) -> tuple[OutcomeStatus, str, list[str]]:
    """Evaluate policy rules against a case.

    Rules are evaluated in order. The first matching rule wins.
    If no rule matches, defaults to human_review for safety.

    Args:
        policy: The loaded policy to apply.
        case: The case to evaluate.

    Returns:
        Tuple of (outcome_status, reason, snippets_used).
    """
    snippets_used: list[str] = []

    for rule in policy.rules:
        matched = _evaluate_condition(rule.condition, case)
        if matched:
            snippets_used.append(rule.name)
            return rule.outcome, rule.reason, snippets_used

    # Safety default: if no rule matches, require human review
    return (
        OutcomeStatus.HUMAN_REVIEW,
        "nenhuma regra aplicável — revisão humana obrigatória",
        snippets_used,
    )


def build_prompt(policy: Policy, case: CaseEnvelope) -> str:
    """Build the LLM prompt from policy template and case context.

    The prompt template uses {description} and {policy_context}
    placeholders. policy_context is a summary of the applicable
    rules in human-readable format.
    """
    policy_context = _build_policy_context(policy)
    template = policy.prompt_template or _DEFAULT_TEMPLATE

    return template.format(
        description=case.description,
        policy_context=policy_context,
        issue_type=case.issue_type.value,
        product_line=case.product_line.value,
        customer_tier=case.customer_tier.value,
    )


# ── Internal helpers ──────────────────────


_DEFAULT_TEMPLATE = (
    "Você é um assistente de operações financeiras.\n"
    "Tipo de caso: {issue_type}\n"
    "Produto: {product_line}\n"
    "Segmento do cliente: {customer_tier}\n"
    "Contexto do caso: {description}\n"
    "Política aplicável:\n{policy_context}\n"
    "Responda de forma clara, objetiva e profissional."
)


def _evaluate_condition(
    condition: str,
    case: CaseEnvelope,
) -> bool:
    """Evaluate a simple condition string against a case.

    Supported conditions:
        "default"                  — always matches
        "valor_brl > N"            — numeric comparison
        "valor_brl < N"            — numeric comparison
        "no_documents"             — case has no documents
        "has_risk_flag:FLAG"       — specific risk flag present
        "customer_tier:TIER"       — customer tier matches
        "has_documents"            — case has documents

    This is deliberately simple. Complex conditions should be
    decomposed into multiple rules in the YAML, not encoded
    in a mini-language.
    """
    condition = condition.strip()

    if condition == "default":
        return True

    if condition == "no_documents":
        return len(case.documents) == 0

    if condition == "has_documents":
        return len(case.documents) > 0

    if condition.startswith("has_risk_flag:"):
        flag = condition.split(":", 1)[1].strip()
        return flag in case.risk_flags

    if condition.startswith("customer_tier:"):
        tier = condition.split(":", 1)[1].strip()
        return case.customer_tier.value == tier

    if "valor_brl" in condition:
        return _eval_numeric_condition(
            condition, case.valor_brl
        )

    return False


def _eval_numeric_condition(
    condition: str,
    value: float | None,
) -> bool:
    """Evaluate a numeric condition like 'valor_brl > 500'."""
    if value is None:
        return False

    parts = condition.replace("valor_brl", "").strip()

    if parts.startswith(">"):
        threshold = float(parts[1:].strip())
        return value > threshold
    if parts.startswith("<"):
        threshold = float(parts[1:].strip())
        return value < threshold
    if parts.startswith(">="):
        threshold = float(parts[2:].strip())
        return value >= threshold
    if parts.startswith("<="):
        threshold = float(parts[2:].strip())
        return value <= threshold

    return False


def _build_policy_context(policy: Policy) -> str:
    """Build human-readable policy context for the prompt."""
    lines = []
    for rule in policy.rules:
        lines.append(
            f"- {rule.name}: se {rule.condition}, "
            f"então {rule.outcome.value} "
            f"({rule.reason})"
        )
    return "\n".join(lines)

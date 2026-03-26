"""Case resolver — orchestrates policy lookup, LLM call, and outcome.

This is the entry point for case resolution. It:
1. Looks up the applicable policy by issue_type
2. Evaluates policy rules to determine outcome status
3. If not blocked, calls the LLM for a response draft
4. Assembles the CaseOutcome with full provenance

The LLM call goes through a completer function. The default
completer uses llmscope's call_llm(). Tests inject a mock.
This makes the resolver testable without any LLM SDK installed.

Usage:
    from caseledger import resolve_case, CaseEnvelope

    outcome = await resolve_case(case, policies_dir="policies/")
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Protocol

from caseledger.case import CaseEnvelope
from caseledger.outcomes import CaseOutcome, OutcomeStatus
from caseledger.policy import (
    Policy,
    build_prompt,
    evaluate_policy,
    load_policies_from_dir,
)


class Completer(Protocol):
    """Protocol for the LLM completion function.

    Default: llmscope's call_llm wrapped in an adapter.
    Tests: inject a mock that returns static text.
    """

    async def __call__(
        self,
        prompt: str,
        model_tier: str,
        route_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> CompletionResult:
        ...


class CompletionResult:
    """Normalized result from any LLM completion."""

    def __init__(
        self,
        text: str,
        model: str = "mock",
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        request_id: str = "",
    ) -> None:
        self.text = text
        self.model = model
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.request_id = request_id


def _default_completer() -> Any:
    """Try to import llmscope's call_llm. Return None if unavailable."""
    try:
        from llmscope import call_llm

        return call_llm
    except ImportError:
        return None


async def _call_with_llmscope(
    llm_call: Any,
    prompt: str,
    model_tier: str,
    case: CaseEnvelope,
) -> CompletionResult:
    """Adapter: call llmscope and normalize the result."""
    result = await llm_call(
        prompt=prompt,
        model_tier=model_tier,
        route_name="/answer-routed",
        metadata={
            "case_id": case.case_id,
            "issue_type": case.issue_type.value,
            "product_line": case.product_line.value,
        },
    )
    return CompletionResult(
        text=result.text,
        model=result.selected_model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.estimated_cost_usd,
        request_id=result.request_id,
    )


def _select_model_tier(
    case: CaseEnvelope,
    outcome_status: OutcomeStatus,
) -> str:
    """Select model tier based on case context.

    Human review cases use expensive model for quality.
    Suggested responses use cheap model for cost efficiency.
    Blocked cases don't call LLM at all.
    """
    if outcome_status == OutcomeStatus.HUMAN_REVIEW:
        return "expensive"
    if case.customer_tier.value in ("personalite", "private"):
        return "expensive"
    return "cheap"


async def resolve_case(
    case: CaseEnvelope,
    policies_dir: str | Path = "policies",
    completer: Any | None = None,
) -> CaseOutcome:
    """Resolve a case end-to-end.

    1. Load policies and find the one matching case.issue_type
    2. Evaluate policy rules to determine outcome status
    3. If not blocked, call LLM for response draft
    4. Assemble CaseOutcome with provenance

    Args:
        case: The case to resolve.
        policies_dir: Path to directory with YAML policies.
        completer: Optional LLM completer. Uses llmscope if None.

    Returns:
        CaseOutcome with decision, provenance, and cost.
    """
    policies = load_policies_from_dir(Path(policies_dir))

    policy = policies.get(case.issue_type.value)
    if policy is None:
        return CaseOutcome(
            case_id=case.case_id,
            status=OutcomeStatus.BLOCKED,
            response_text=None,
            decision_reason=(
                f"no policy defined for "
                f"{case.issue_type.value}"
            ),
            policy_id="none",
            policy_version="0.0",
        )

    # Evaluate policy rules
    outcome_status, reason, snippets = evaluate_policy(
        policy, case
    )

    # If blocked, skip LLM call entirely
    if outcome_status == OutcomeStatus.BLOCKED:
        return CaseOutcome(
            case_id=case.case_id,
            status=OutcomeStatus.BLOCKED,
            response_text=None,
            decision_reason=reason,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            policy_snippets_used=snippets,
        )

    # Build prompt and call LLM
    prompt = build_prompt(policy, case)
    model_tier = _select_model_tier(case, outcome_status)

    if completer is not None:
        # Use injected completer (tests or custom)
        completion = await completer(
            prompt=prompt,
            model_tier=model_tier,
            route_name="/answer-routed",
            metadata={"case_id": case.case_id},
        )
        if isinstance(completion, CompletionResult):
            comp_result = completion
        else:
            # Adapt llmscope GatewayResult
            comp_result = CompletionResult(
                text=completion.text,
                model=completion.selected_model,
                tokens_in=completion.tokens_in,
                tokens_out=completion.tokens_out,
                cost_usd=completion.estimated_cost_usd,
                request_id=completion.request_id,
            )
    else:
        # Try llmscope default
        llm_call = _default_completer()
        if llm_call is None:
            return CaseOutcome(
                case_id=case.case_id,
                status=OutcomeStatus.BLOCKED,
                response_text=None,
                decision_reason=(
                    "llmscope not installed — "
                    "cannot make LLM call"
                ),
                policy_id=policy.policy_id,
                policy_version=policy.version,
                policy_snippets_used=snippets,
            )
        comp_result = await _call_with_llmscope(
            llm_call, prompt, model_tier, case
        )

    return CaseOutcome(
        case_id=case.case_id,
        status=outcome_status,
        response_text=comp_result.text,
        decision_reason=reason,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_snippets_used=snippets,
        model_selected=comp_result.model,
        cost_usd=comp_result.cost_usd,
        tokens_in=comp_result.tokens_in,
        tokens_out=comp_result.tokens_out,
        trace_id=comp_result.request_id,
        confidence=0.85 if outcome_status == OutcomeStatus.SUGGESTED else 0.60,
    )

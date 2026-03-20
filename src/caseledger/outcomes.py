"""Outcome types for case resolution.

Every case resolves to exactly one of three outcomes:
- SuggestedResponse: automation proposes an answer
- HumanReview: automation drafts but requires approval
- Blocked: automation stops, case escalated without response

The outcome carries full provenance: which policy was applied,
which model served, what the confidence was, and why the system
decided what it decided. This is the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class OutcomeStatus(StrEnum):
    """Terminal status of a case resolution."""

    SUGGESTED = "suggested_response"
    HUMAN_REVIEW = "human_review"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CaseOutcome:
    """Immutable result of case resolution with full provenance.

    Every field exists for auditability. A compliance officer
    should be able to read this and understand: what happened,
    why, based on what, and at what cost.
    """

    # Decision
    case_id: str
    status: OutcomeStatus
    response_text: str | None
    decision_reason: str

    # Policy provenance
    policy_id: str
    policy_version: str
    policy_snippets_used: list[str] = field(
        default_factory=list
    )

    # Model provenance (from llmscope)
    model_selected: str | None = None
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: float | None = None
    trace_id: str | None = None

    # Confidence
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging and API response."""
        result: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if isinstance(value, StrEnum):
                result[key] = value.value
            elif value is not None:
                result[key] = value
        return result

    @property
    def requires_human(self) -> bool:
        """True if outcome needs human approval."""
        return self.status == OutcomeStatus.HUMAN_REVIEW

    @property
    def is_automated(self) -> bool:
        """True if response can be sent without review."""
        return self.status == OutcomeStatus.SUGGESTED

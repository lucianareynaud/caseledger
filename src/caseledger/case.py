"""Case envelope — the central entity of CaseLedger.

Every operation starts with a case. The case carries structured
business context that determines which policy applies, which model
serves the request, and whether the response requires human review.

The case_id is the primary key for everything: telemetry, policy
trace, outcome log, and audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class IssueType(StrEnum):
    """Recognized financial operation categories."""

    CHARGE_DISPUTE = "charge_dispute"
    LIMIT_INCREASE = "limit_increase"
    ONBOARDING_KYC = "onboarding_kyc"
    CARD_REPLACEMENT = "card_replacement"
    TRANSACTION_DECLINED = "transaction_declined"
    DOCUMENTATION_DISPUTE = "documentation_dispute"
    GENERAL_INQUIRY = "general_inquiry"


class CustomerTier(StrEnum):
    """Customer segmentation tiers."""

    STANDARD = "standard"
    PLUS = "plus"
    PERSONALITE = "personalite"
    PRIVATE = "private"


class ProductLine(StrEnum):
    """Financial product lines."""

    CREDIT_CARD = "credit_card"
    CHECKING_ACCOUNT = "checking_account"
    LOAN = "loan"
    INVESTMENT = "investment"
    INSURANCE = "insurance"


@dataclass
class CaseEnvelope:
    """Structured business context for a financial operations case.

    This is NOT a prompt. It is the typed input contract that
    determines policy selection, model routing, and outcome
    classification. The resolver consumes this to build the
    prompt, call the LLM via llmscope, apply policy, and
    produce an outcome.

    Required fields have no defaults. Optional fields default
    to None or empty. Adding optional fields is non-breaking.
    """

    # Identity
    case_id: str
    issue_type: IssueType
    product_line: ProductLine
    customer_tier: CustomerTier
    description: str

    # Context
    risk_flags: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    customer_history_summary: str | None = None
    amount_brl: float | None = None

    # Metadata
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    source_channel: str = "api"
    language: str = "pt-BR"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging and telemetry."""
        result: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if isinstance(value, StrEnum):
                result[key] = value.value
            elif value is not None:
                result[key] = value
        return result

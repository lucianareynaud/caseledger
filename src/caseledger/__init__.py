"""CaseLedger — Policy-bounded decision traces for AI-assisted financial operations."""

from caseledger.case import (
    CaseEnvelope,
    CustomerTier,
    IssueType,
    ProductLine,
)
from caseledger.outcomes import CaseOutcome, OutcomeStatus
from caseledger.policy import (
    Policy,
    PolicyRule,
    evaluate_policy,
    load_policies_from_dir,
    load_policy,
)
from caseledger.resolver import CompletionResult, resolve_case

__version__ = "0.1.0"

__all__ = [
    "CaseEnvelope",
    "CaseOutcome",
    "CompletionResult",
    "CustomerTier",
    "IssueType",
    "OutcomeStatus",
    "Policy",
    "PolicyRule",
    "ProductLine",
    "__version__",
    "evaluate_policy",
    "load_policies_from_dir",
    "load_policy",
    "resolve_case",
]

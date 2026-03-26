"""Tests for CaseLedger core.

Tests verify:
1. Case envelope creation and serialization
2. Policy loading and rule evaluation
3. Outcome determination for all three statuses
4. Resolver orchestration with mock completer
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from caseledger.case import (
    CaseEnvelope,
    CustomerTier,
    IssueType,
    ProductLine,
)
from caseledger.outcomes import CaseOutcome, OutcomeStatus
from caseledger.policy import (
    evaluate_policy,
    load_policy,
)
from caseledger.resolver import CompletionResult, resolve_case


def _make_case(**overrides) -> CaseEnvelope:
    """Build a test case with sensible defaults."""
    defaults = {
        "case_id": "TEST-001",
        "issue_type": IssueType.CHARGE_DISPUTE,
        "product_line": ProductLine.CREDIT_CARD,
        "customer_tier": CustomerTier.STANDARD,
        "description": "Duplicate charge of R$180",
        "documents": ["invoice.pdf"],
        "amount_brl": 180.0,
    }
    defaults.update(overrides)
    return CaseEnvelope(**defaults)


def _write_policy(path: Path, policy_dict: dict) -> Path:
    """Write a policy YAML and return path."""
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(policy_dict, fh, allow_unicode=True)
    return path


def _simple_policy() -> dict:
    """Minimal policy for testing."""
    return {
        "policy_id": "charge_dispute",
        "version": "1.0",
        "rules": [
            {
                "name": "high_value",
                "condition": "amount_brl > 500",
                "outcome": "human_review",
                "reason": "high value",
            },
            {
                "name": "no_docs",
                "condition": "no_documents",
                "outcome": "blocked",
                "reason": "no documentation",
            },
            {
                "name": "default",
                "condition": "default",
                "outcome": "suggested_response",
                "reason": "within parameters",
            },
        ],
        "prompt_template": "Case: {description}",
    }


async def _mock_completer(
    prompt: str,
    model_tier: str,
    route_name: str,
    metadata: dict | None = None,
) -> CompletionResult:
    return CompletionResult(
        text="Mock response for testing.",
        model="gpt-4o-mini",
        tokens_in=10,
        tokens_out=15,
        cost_usd=0.0001,
        request_id="mock-123",
    )


class TestCaseEnvelope:
    """Case creation and serialization."""

    def test_create_minimal(self):
        case = _make_case()
        assert case.case_id == "TEST-001"
        assert case.issue_type == IssueType.CHARGE_DISPUTE

    def test_to_dict(self):
        case = _make_case()
        d = case.to_dict()
        assert d["case_id"] == "TEST-001"
        assert d["issue_type"] == "charge_dispute"
        assert d["product_line"] == "credit_card"
        assert "created_at" in d

    def test_risk_flags_default_empty(self):
        case = _make_case()
        assert case.risk_flags == []

    def test_amount_brl_optional(self):
        case = _make_case(amount_brl=None)
        d = case.to_dict()
        assert "amount_brl" not in d


class TestPolicyLoading:
    """Policy YAML loading."""

    def test_load_policy(self, tmp_path):
        path = tmp_path / "test.yaml"
        _write_policy(path, _simple_policy())
        policy = load_policy(path)
        assert policy.policy_id == "charge_dispute"
        assert policy.version == "1.0"
        assert len(policy.rules) == 3

    def test_rule_types(self, tmp_path):
        path = tmp_path / "test.yaml"
        _write_policy(path, _simple_policy())
        policy = load_policy(path)
        assert (
            policy.rules[0].outcome
            == OutcomeStatus.HUMAN_REVIEW
        )
        assert (
            policy.rules[1].outcome == OutcomeStatus.BLOCKED
        )
        assert (
            policy.rules[2].outcome
            == OutcomeStatus.SUGGESTED
        )


class TestPolicyEvaluation:
    """Policy rule evaluation against cases."""

    def _load(self, tmp_path):
        path = tmp_path / "test.yaml"
        _write_policy(path, _simple_policy())
        return load_policy(path)

    def test_suggested_response(self, tmp_path):
        policy = self._load(tmp_path)
        case = _make_case(
            amount_brl=180.0, documents=["f.pdf"]
        )
        status, reason, snippets = evaluate_policy(
            policy, case
        )
        assert status == OutcomeStatus.SUGGESTED

    def test_human_review_high_value(self, tmp_path):
        policy = self._load(tmp_path)
        case = _make_case(amount_brl=1500.0)
        status, reason, snippets = evaluate_policy(
            policy, case
        )
        assert status == OutcomeStatus.HUMAN_REVIEW
        assert "high_value" in snippets

    def test_blocked_no_documents(self, tmp_path):
        policy = self._load(tmp_path)
        case = _make_case(documents=[], amount_brl=100.0)
        status, reason, snippets = evaluate_policy(
            policy, case
        )
        assert status == OutcomeStatus.BLOCKED


class TestResolver:
    """End-to-end resolver with mock completer."""

    async def test_suggested_response(self, tmp_path):
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        _write_policy(
            policy_dir / "charge_dispute.yaml",
            _simple_policy(),
        )

        case = _make_case(amount_brl=180.0)
        outcome = await resolve_case(
            case=case,
            policies_dir=str(policy_dir),
            completer=_mock_completer,
        )

        assert outcome.status == OutcomeStatus.SUGGESTED
        assert outcome.response_text is not None
        assert outcome.policy_id == "charge_dispute"
        assert outcome.model_selected == "gpt-4o-mini"
        assert outcome.cost_usd == 0.0001

    async def test_human_review(self, tmp_path):
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        _write_policy(
            policy_dir / "charge_dispute.yaml",
            _simple_policy(),
        )

        case = _make_case(amount_brl=2000.0)
        outcome = await resolve_case(
            case=case,
            policies_dir=str(policy_dir),
            completer=_mock_completer,
        )

        assert outcome.status == OutcomeStatus.HUMAN_REVIEW
        assert outcome.response_text is not None
        assert outcome.requires_human is True

    async def test_blocked(self, tmp_path):
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        _write_policy(
            policy_dir / "charge_dispute.yaml",
            _simple_policy(),
        )

        case = _make_case(documents=[], amount_brl=100.0)
        outcome = await resolve_case(
            case=case,
            policies_dir=str(policy_dir),
            completer=_mock_completer,
        )

        assert outcome.status == OutcomeStatus.BLOCKED
        assert outcome.response_text is None

    async def test_no_policy_blocks(self, tmp_path):
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()

        case = _make_case(
            issue_type=IssueType.TRANSACTION_DECLINED
        )
        outcome = await resolve_case(
            case=case,
            policies_dir=str(policy_dir),
            completer=_mock_completer,
        )

        assert outcome.status == OutcomeStatus.BLOCKED

    async def test_outcome_provenance(self, tmp_path):
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        _write_policy(
            policy_dir / "charge_dispute.yaml",
            _simple_policy(),
        )

        case = _make_case()
        outcome = await resolve_case(
            case=case,
            policies_dir=str(policy_dir),
            completer=_mock_completer,
        )

        d = outcome.to_dict()
        assert "policy_id" in d
        assert "policy_version" in d
        assert "decision_reason" in d
        assert "case_id" in d


class TestOutcomeProperties:
    """Outcome helper properties."""

    def test_requires_human(self):
        outcome = CaseOutcome(
            case_id="T",
            status=OutcomeStatus.HUMAN_REVIEW,
            response_text="draft",
            decision_reason="test",
            policy_id="p",
            policy_version="1.0",
        )
        assert outcome.requires_human is True
        assert outcome.is_automated is False

    def test_is_automated(self):
        outcome = CaseOutcome(
            case_id="T",
            status=OutcomeStatus.SUGGESTED,
            response_text="answer",
            decision_reason="test",
            policy_id="p",
            policy_version="1.0",
        )
        assert outcome.is_automated is True
        assert outcome.requires_human is False

    def test_blocked_neither(self):
        outcome = CaseOutcome(
            case_id="T",
            status=OutcomeStatus.BLOCKED,
            response_text=None,
            decision_reason="test",
            policy_id="p",
            policy_version="1.0",
        )
        assert outcome.is_automated is False
        assert outcome.requires_human is False

"""Case submission and inspection endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from caseledger.case import (
    CaseEnvelope,
    CustomerTier,
    IssueType,
    ProductLine,
)
from caseledger.resolver import CompletionResult, resolve_case

router = APIRouter()

# In-memory store for demo purposes
_case_log: dict[str, dict[str, Any]] = {}


class CaseRequest(BaseModel):
    """API request to submit a case."""

    case_id: str = Field(..., min_length=1)
    issue_type: str
    product_line: str
    customer_tier: str
    description: str = Field(..., min_length=1)
    risk_flags: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    amount_brl: float | None = None


async def _mock_completer(
    prompt: str,
    model_tier: str,
    route_name: str,
    metadata: dict[str, Any] | None = None,
) -> CompletionResult:
    """Mock completer for demo without LLM API key."""
    return CompletionResult(
        text=(
            "Based on the case analysis and applicable policy, "
            "we have identified that the request is within "
            "operational parameters. We recommend processing "
            "according to standard procedure."
        ),
        model="mock-demo",
        tokens_in=50,
        tokens_out=40,
        cost_usd=0.0001,
        request_id="demo-request-id",
    )


@router.post("/cases/submit")
async def submit_case(request: CaseRequest) -> dict:
    """Submit a case for resolution."""
    try:
        case = CaseEnvelope(
            case_id=request.case_id,
            issue_type=IssueType(request.issue_type),
            product_line=ProductLine(request.product_line),
            customer_tier=CustomerTier(request.customer_tier),
            description=request.description,
            risk_flags=request.risk_flags,
            documents=request.documents,
            amount_brl=request.amount_brl,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid case data: {exc}",
        ) from exc

    outcome = await resolve_case(
        case=case,
        policies_dir="policies",
        completer=_mock_completer,
    )

    result = outcome.to_dict()
    _case_log[case.case_id] = {
        "case": case.to_dict(),
        "outcome": result,
    }

    return result


@router.get("/cases/{case_id}")
def inspect_case(case_id: str) -> dict:
    """Inspect a previously resolved case."""
    if case_id not in _case_log:
        raise HTTPException(
            status_code=404,
            detail=f"Case {case_id} not found",
        )
    return _case_log[case_id]


@router.get("/cases")
def list_cases() -> dict:
    """List all resolved cases."""
    return {
        "total": len(_case_log),
        "cases": list(_case_log.keys()),
    }

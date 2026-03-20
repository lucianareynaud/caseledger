"""CaseLedger reference API.

Run: uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.routes import cases

app = FastAPI(
    title="CaseLedger",
    version="0.1.0",
    description=(
        "Policy-bounded decision traces for "
        "AI-assisted financial operations"
    ),
)

app.include_router(cases.router, tags=["cases"])


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok"}

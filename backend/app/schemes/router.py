from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.database import get_db
from app.models.models import GovernmentScheme
from app.schemas.schemas import SchemeOut, SchemeCalculationRequest, SchemeCalculationResponse
from app.auth.security import get_current_user
from app.models.models import User

router = APIRouter(prefix="/schemes", tags=["Schemes"])

@router.get("", response_model=list[SchemeOut])
def get_schemes(
    business_type: Optional[str] = Query(None),
    location_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns verified schemes. UI MUST show 'Potentially relevant — not a guarantee of eligibility'."""
    schemes = db.query(GovernmentScheme).all()
    return schemes

@router.post("/calculate", response_model=SchemeCalculationResponse)
def calculate_scheme_indicative(
    payload: SchemeCalculationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Indicative-only calculation. All numbers sourced from verified scheme table, never LLM."""
    scheme = db.query(GovernmentScheme).filter(GovernmentScheme.id == payload.scheme_id).first()
    if not scheme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Scheme not found")

    govt_contribution = round(payload.loan_amount * (scheme.contribution_pct / 100.0), 2)
    beneficiary_contribution = round(payload.loan_amount - govt_contribution, 2)

    # Simple EMI: EMI = P*r*(1+r)^n / ((1+r)^n -1)
    def emi(principal, annual_rate_pct, years):
        r = annual_rate_pct / (12 * 100)
        n = years * 12
        if r == 0:
            return round(principal / n, 2)
        return round(principal * r * (1 + r)**n / ((1 + r)**n - 1), 2)

    emi_low = emi(beneficiary_contribution, scheme.indicative_rate_low, scheme.tenure_years)
    emi_high = emi(beneficiary_contribution, scheme.indicative_rate_high, scheme.tenure_years)

    return {
        "scheme_name": scheme.name,
        "requested_amount": payload.loan_amount,
        "government_contribution": govt_contribution,
        "beneficiary_contribution": beneficiary_contribution,
        "indicative_monthly_emi_low": emi_low,
        "indicative_monthly_emi_high": emi_high,
        "tenure_years": scheme.tenure_years,
        "source_url": scheme.source_url,
        "disclaimer": "Potentially relevant — indicative rates only. Final eligibility depends on official appraisal."
    }

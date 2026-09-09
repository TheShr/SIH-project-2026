from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User
from app.schemas.schemas import AIExplainRequest, AIExplainResponse
from app.auth.security import get_current_user
from app.ai.explanation_service import generate_explanation

router = APIRouter(prefix="/ai", tags=["AI Explanation"])

@router.post("/explain", response_model=AIExplainResponse)
def ai_explain(
    payload: AIExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evidence-to-Explanation pipeline with mandatory guardrail.
    LLM never produces scores or numbers. Template fallback always exists.
    """
    evidence_dict = payload.evidence_object.model_dump()
    explanation_text, is_fallback = generate_explanation(db, evidence_dict, user_id=current_user.id)

    return {
        "explanation_text": explanation_text,
        "is_fallback": is_fallback,
        "evidence_chips": payload.evidence_object.evidence
    }

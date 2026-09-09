import json
import httpx
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.ai.guardrail import validate_ai_explanation, generate_hinglish_template_fallback
from app.models.models import AnalyticsEvent

def generate_explanation(db: Session, evidence_obj: Dict[str, Any], user_id: int = None) -> Tuple[str, bool]:
    """
    Executes the 3-step explanation pipeline:
    1. Try Ollama local model / Hosted free API
    2. Validate output via guardrail check
    3. If guardrail fails or LLM unreachable, fall back to deterministic Hinglish template
    Returns (explanation_text, is_fallback_flag)
    """
    system_prompt = (
        "You are an AI copilot for rural retail and distribution business owners in India. "
        "Explain the provided evidence object in one short, friendly Hinglish sentence. "
        "CRITICAL RULE: Do NOT add any numbers, percentages, financial amounts, or facts that are not explicitly present in the evidence object below. "
        "Do NOT invent any scheme names or rates."
    )
    
    evidence_json = json.dumps(evidence_obj)

    explanation_text = None
    is_fallback = True

    # 1. Attempt Ollama local call if accessible
    try:
        url = f"{settings.OLLAMA_HOST}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\nEvidence Object:\n{evidence_json}",
            "stream": False
        }
        with httpx.Client(timeout=2.0) as client:
            res = client.post(url, json=payload)
            if res.status_code == 200:
                raw_output = res.json().get("response", "").strip()
                # Run Guardrail Check
                is_valid, reason = validate_ai_explanation(raw_output, evidence_obj)
                if is_valid:
                    explanation_text = raw_output
                    is_fallback = False
                else:
                    # Log rejection event
                    log_event = AnalyticsEvent(
                        user_id=user_id,
                        event_name="ai_guardrail_rejection",
                        payload=json.dumps({"raw_output": raw_output, "reason": reason})
                    )
                    db.add(log_event)
                    db.commit()
    except Exception:
        # Network timeout or Ollama offline — silent fallback
        pass

    # 2. Fall back to deterministic template if LLM path failed or was rejected
    if not explanation_text:
        explanation_text = generate_hinglish_template_fallback(evidence_obj)
        is_fallback = True

    return explanation_text, is_fallback

import re
from typing import List, Dict, Any, Tuple

def extract_numbers_from_text(text: str) -> set[str]:
    """Extract all distinct number sequences (integers or floats) from text."""
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    return set(matches)

def extract_numbers_from_evidence(evidence_obj: Dict[str, Any]) -> set[str]:
    """Extract all numbers explicitly present in the Evidence Object."""
    allowed_numbers = set()
    
    # Score
    if "score" in evidence_obj:
        allowed_numbers.add(str(evidence_obj["score"]))
        
    # Evidence values
    for item in evidence_obj.get("evidence", []):
        val = str(item.get("value", ""))
        # Handle string floats vs int
        allowed_numbers.add(val)
        for num in re.findall(r'\b\d+(?:\.\d+)?\b', val):
            allowed_numbers.add(num)
            
    return allowed_numbers

def validate_ai_explanation(explanation_text: str, evidence_obj: Dict[str, Any], verified_schemes: List[str] = None) -> Tuple[bool, str]:
    """
    Mandatory Guardrail Check:
    1. Returns (True, "") if valid.
    2. Returns (False, reason) if output contains hallucinated numbers or unverified claims.
    """
    text_numbers = extract_numbers_from_text(explanation_text)
    allowed_numbers = extract_numbers_from_evidence(evidence_obj)

    # Check for unauthorized numbers
    unauthorized_numbers = text_numbers - allowed_numbers
    if unauthorized_numbers:
        return False, f"Guardrail rejected: Text contains unauthorized numbers {unauthorized_numbers}"

    # Check for suspicious unverified scheme keywords if any
    suspicious_schemes = ["guaranteed loan", "100% subsidy", "free grant", "0% interest"]
    for kw in suspicious_schemes:
        if kw in explanation_text.lower():
            return False, f"Guardrail rejected: Text contains unverified claim keyword '{kw}'"

    return True, "Valid"

def generate_hinglish_template_fallback(evidence_obj: Dict[str, Any]) -> str:
    """
    Deterministic Hinglish template fallback that interpolates evidence object values.
    Zero hallucination risk. Always succeeds.
    """
    target = evidence_obj.get("target", "Category")
    score = evidence_obj.get("score", 0)
    conf = evidence_obj.get("confidence", "medium").upper()
    
    reporting_count = 0
    suppliers_count = 0
    distance_km = 0
    
    for ev in evidence_obj.get("evidence", []):
        if ev.get("type") in ["retailer_demand_signals", "unique_reporting_retailers"]:
            reporting_count = ev.get("value", 0)
        elif ev.get("type") == "nearby_suppliers":
            suppliers_count = ev.get("value", 0)
        elif ev.get("type") in ["avg_supplier_distance_km", "supplier_distance_km"]:
            distance_km = ev.get("value", 0)

    if evidence_obj.get("recommendation_type") == "opportunity":
        template = (
            f"Aapke area mein {target} ki demand score {score}/100 hai (Confidence: {conf}). "
            f"Aapke paas {reporting_count} local retailers ne demand signal bheja hai. "
            f"Nearby {suppliers_count} suppliers available hain (avg distance {distance_km} km)."
        )
    else:
        template = (
            f"{target} ko stock karne ki recommendation score {score}/100 hai (Confidence: {conf}). "
            f"Local market signals aur {distance_km} km door ke nearby distributor ke base par yeh optimal item match hai."
        )

    return template

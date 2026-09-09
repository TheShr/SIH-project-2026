from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.database import get_db
from app.models.models import User, DemandSignal, Category, RetailerProfile, Location, AnalyticsEvent
from app.auth.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/signals/feed")
def get_signal_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin Signal Monitor – raw demand signals feed for demo visibility."""
    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")

    signals = (
        db.query(DemandSignal)
        .order_by(desc(DemandSignal.created_at))
        .limit(100)
        .all()
    )

    result = []
    for s in signals:
        retailer = s.retailer
        loc = retailer.location if retailer else None
        cat = s.category
        result.append({
            "id": s.id,
            "source": s.source,
            "category": cat.name if cat else "Unknown",
            "village": loc.village_name if loc else "Unknown",
            "block": loc.block if loc else "",
            "created_at": s.created_at.isoformat()
        })

    return {"signals": result, "total": len(result)}

@router.get("/guardrail-rejections")
def get_guardrail_rejections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns AI guardrail rejection events for monitoring."""
    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")

    events = (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.event_name == "ai_guardrail_rejection")
        .order_by(desc(AnalyticsEvent.created_at))
        .limit(50)
        .all()
    )
    return {
        "rejections": [{"id": e.id, "payload": e.payload, "created_at": e.created_at.isoformat()} for e in events],
        "total": len(events)
    }

@router.get("/opportunities/summary")
def get_opportunities_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.models import Category, Location
    from app.opportunities.opportunity_engine import compute_opportunity

    if current_user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin only")

    cats = db.query(Category).all()
    locs = db.query(Location).all()
    results = []
    for loc in locs:
        for cat in cats:
            try:
                opp = compute_opportunity(db, loc.id, cat.id)
                if opp["opportunity_score"] > 0:
                    results.append(opp)
            except Exception:
                continue
    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return {"opportunities": results[:20]}

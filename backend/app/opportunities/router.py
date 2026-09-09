from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Location, Category
from app.auth.security import get_current_user
from app.opportunities.opportunity_engine import compute_opportunity

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

@router.get("/{location_id}/{category_id}")
def get_opportunity_detail(
    location_id: int,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    opp = compute_opportunity(db, location_id, category_id)
    return opp

@router.get("/location/{location_id}")
def get_all_opportunities_for_location(
    location_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    categories = db.query(Category).all()
    opps = []
    for cat in categories:
        try:
            opp = compute_opportunity(db, location_id, cat.id)
            if opp["opportunity_score"] > 0:
                opps.append(opp)
        except Exception:
            continue

    opps.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return {"location": {"id": location.id, "village_name": location.village_name}, "opportunities": opps}

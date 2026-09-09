from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db, haversine_km
from app.models.models import User, Location, DistributorProfile, Category, CatalogueItem, Product
from app.schemas.schemas import DistributorOnboarding, DistributorProfileOut, CatalogueItemCreate, CatalogueItemOut
from app.auth.security import get_current_user
from app.opportunities.opportunity_engine import compute_opportunity

router = APIRouter(prefix="/distributors", tags=["Distributors"])

@router.post("/onboarding", response_model=DistributorProfileOut)
def distributor_onboarding(
    payload: DistributorOnboarding,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "distributor":
        raise HTTPException(status_code=403, detail="Only distributor role can complete distributor onboarding")

    location = db.query(Location).filter(
        Location.village_name.ilike(payload.village_name.strip()),
        Location.block.ilike(payload.block.strip())
    ).first()

    if not location:
        location = db.query(Location).filter(Location.block.ilike(payload.block.strip())).first()
        if not location:
            location = Location(
                village_name=payload.village_name,
                block=payload.block,
                district=payload.district,
                lat=28.4595,
                lng=77.0266
            )
            db.add(location)
            db.commit()
            db.refresh(location)

    profile = db.query(DistributorProfile).filter(DistributorProfile.user_id == current_user.id).first()
    if profile:
        profile.business_name = payload.business_name
        profile.location_id = location.id
        profile.service_radius_km = payload.service_radius_km
        profile.moq_default = payload.moq_default
    else:
        profile = DistributorProfile(
            user_id=current_user.id,
            business_name=payload.business_name,
            location_id=location.id,
            service_radius_km=payload.service_radius_km,
            moq_default=payload.moq_default
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

@router.get("/{distributor_id}/dashboard")
def get_distributor_dashboard(
    distributor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(DistributorProfile).filter(DistributorProfile.id == distributor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Distributor profile not found")

    categories = db.query(Category).all()
    opps = []
    for cat in categories:
        # Only compute opportunities for locations this distributor can serve
        all_locs = db.query(Location).all()
        for loc in all_locs:
            dist_km = haversine_km(profile.location.lat, profile.location.lng, loc.lat, loc.lng)
            if dist_km <= profile.service_radius_km:
                try:
                    opp = compute_opportunity(db, loc.id, cat.id)
                    opps.append(opp)
                except Exception:
                    continue

    opps.sort(key=lambda x: x["opportunity_score"], reverse=True)
    top_opps = opps[:5]

    catalogue_count = db.query(CatalogueItem).filter(CatalogueItem.distributor_id == distributor_id).count()

    from app.models.models import Order
    pending_orders = db.query(Order).filter(
        Order.distributor_id == distributor_id,
        Order.status == "requested"
    ).count()

    return {
        "distributor": {
            "id": profile.id,
            "business_name": profile.business_name,
            "location": profile.location.village_name,
            "service_radius_km": profile.service_radius_km
        },
        "top_opportunities": top_opps,
        "catalogue_count": catalogue_count,
        "pending_orders": pending_orders
    }

@router.get("/{distributor_id}/opportunities")
def get_distributor_opportunities(
    distributor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(DistributorProfile).filter(DistributorProfile.id == distributor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Distributor profile not found")

    categories = db.query(Category).all()
    all_locs = db.query(Location).all()
    opps = []

    for cat in categories:
        for loc in all_locs:
            dist_km = haversine_km(profile.location.lat, profile.location.lng, loc.lat, loc.lng)
            if dist_km <= profile.service_radius_km:
                try:
                    opp = compute_opportunity(db, loc.id, cat.id)
                    if opp["opportunity_score"] > 0:
                        opps.append(opp)
                except Exception:
                    continue

    opps.sort(key=lambda x: x["opportunity_score"], reverse=True)
    # Deduplicate by category (take highest per category)
    seen_cats = {}
    unique_opps = []
    for o in opps:
        if o["category_id"] not in seen_cats:
            seen_cats[o["category_id"]] = True
            unique_opps.append(o)

    return {"opportunities": unique_opps}

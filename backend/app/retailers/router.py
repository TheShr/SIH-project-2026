from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Location, RetailerProfile, Category, Product, DemandSignal, Order
from app.schemas.schemas import RetailerOnboarding, RetailerProfileOut, StockPlanResponse, DemandSignalCreate, DemandSignalOut
from app.auth.security import get_current_user
from app.recommendations.stock_engine import compute_smart_stock_plan
from app.opportunities.opportunity_engine import compute_opportunity

router = APIRouter(prefix="/retailers", tags=["Retailers"])

@router.post("/onboarding", response_model=RetailerProfileOut)
def retailer_onboarding(
    payload: RetailerOnboarding,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "retailer":
        raise HTTPException(status_code=403, detail="Only retailer role can complete retailer onboarding")

    # Match or create location cell
    location = db.query(Location).filter(
        Location.village_name.ilike(payload.village_name.strip()),
        Location.block.ilike(payload.block.strip())
    ).first()

    if not location:
        # Fallback location lookup by block or default coords
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

    # Check if profile exists or update
    profile = db.query(RetailerProfile).filter(RetailerProfile.user_id == current_user.id).first()
    if profile:
        profile.business_type = payload.business_type
        profile.location_id = location.id
        profile.budget = payload.budget
    else:
        profile = RetailerProfile(
            user_id=current_user.id,
            business_type=payload.business_type,
            location_id=location.id,
            budget=payload.budget
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    # Ingest unmet demand answer as primary demand_signal (Source = onboarding)
    cat = db.query(Category).filter(Category.name.ilike(payload.unmet_demand_category.strip())).first()
    if not cat:
        cat = Category(name=payload.unmet_demand_category.strip())
        db.add(cat)
        db.commit()
        db.refresh(cat)

    signal = DemandSignal(
        retailer_id=profile.id,
        category_id=cat.id,
        source="onboarding",
        weight_hint="raw"
    )
    db.add(signal)
    db.commit()

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "business_type": profile.business_type,
        "location_id": profile.location_id,
        "village_name": location.village_name,
        "block": location.block,
        "district": location.district,
        "budget": profile.budget,
        "business_age_months": profile.business_age_months
    }

@router.get("/{retailer_id}/dashboard")
def get_retailer_dashboard(
    retailer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(RetailerProfile).filter(RetailerProfile.id == retailer_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Retailer profile not found")

    location = profile.location
    categories = db.query(Category).all()

    # Top opportunities near retailer
    opps = []
    for cat in categories:
        try:
            opp_res = compute_opportunity(db, location.id, cat.id)
            opps.append(opp_res)
        except Exception:
            continue

    opps.sort(key=lambda x: x["opportunity_score"], reverse=True)
    top_opportunities = opps[:5]

    # Quick stock plan summary
    stock_plan = compute_smart_stock_plan(db, retailer_id)

    # Recent orders
    recent_orders = db.query(Order).filter(Order.retailer_id == retailer_id).order_by(Order.created_at.desc()).limit(5).all()
    order_list = []
    for o in recent_orders:
        dist = o.distributor
        order_list.append({
            "id": o.id,
            "distributor_name": dist.business_name if dist else "Distributor",
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at.isoformat()
        })

    return {
        "retailer": {
            "id": profile.id,
            "business_type": profile.business_type,
            "village_name": location.village_name,
            "block": location.block,
            "district": location.district,
            "budget": profile.budget
        },
        "top_opportunities": top_opportunities,
        "stock_plan_summary": {
            "budget_allocated": stock_plan["budget_allocated"],
            "item_count": len(stock_plan["items"])
        },
        "recent_orders": order_list
    }

@router.get("/{retailer_id}/stock-plan", response_model=StockPlanResponse)
def get_retailer_stock_plan(
    retailer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(RetailerProfile).filter(RetailerProfile.id == retailer_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Retailer profile not found")

    plan = compute_smart_stock_plan(db, retailer_id)
    return plan

@router.post("/{retailer_id}/demand-signal", response_model=DemandSignalOut)
def post_demand_signal(
    retailer_id: int,
    payload: DemandSignalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(RetailerProfile).filter(RetailerProfile.id == retailer_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Retailer profile not found")

    cat = db.query(Category).filter(Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    signal = DemandSignal(
        retailer_id=retailer_id,
        category_id=payload.category_id,
        product_id=payload.product_id,
        source=payload.source,
        weight_hint="raw"
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    return {
        "id": signal.id,
        "retailer_id": signal.retailer_id,
        "category_id": signal.category_id,
        "category_name": cat.name,
        "product_id": signal.product_id,
        "source": signal.source,
        "created_at": signal.created_at
    }

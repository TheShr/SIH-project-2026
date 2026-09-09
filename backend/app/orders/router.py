from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Order, OrderItem, Product, RetailerProfile, DistributorProfile, AuditLog, DemandSignal
from app.schemas.schemas import OrderCreate, OrderStatusUpdate, OrderOut, OrderItemOut
from app.auth.security import get_current_user
from app.orders.reorder_engine import compute_reorder_suggestion
from datetime import datetime

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("", response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    retailer = db.query(RetailerProfile).filter(RetailerProfile.user_id == current_user.id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="Retailer profile not found")

    distributor = db.query(DistributorProfile).filter(DistributorProfile.id == payload.distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    total_amount = sum(item.qty * item.unit_price for item in payload.items)

    order = Order(
        retailer_id=retailer.id,
        distributor_id=payload.distributor_id,
        status="requested",
        total_amount=total_amount
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    for item_in in payload.items:
        product = db.query(Product).filter(Product.id == item_in.product_id).first()
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_in.product_id,
            qty=item_in.qty,
            unit_price=item_in.unit_price
        )
        db.add(order_item)
        # Also create an order demand signal
        if product:
            signal = DemandSignal(
                retailer_id=retailer.id,
                category_id=product.category_id,
                product_id=product.id,
                source="order",
                weight_hint="derived"
            )
            db.add(signal)

    audit = AuditLog(user_id=current_user.id, action="order_created", entity="orders", entity_id=order.id)
    db.add(audit)
    db.commit()
    db.refresh(order)

    items_out = [{"id": i.id, "product_id": i.product_id, "product_name": i.product.name if i.product else None, "qty": i.qty, "unit_price": i.unit_price} for i in order.items]
    return {
        "id": order.id,
        "retailer_id": order.retailer_id,
        "distributor_id": order.distributor_id,
        "distributor_name": distributor.business_name,
        "status": order.status,
        "total_amount": order.total_amount,
        "created_at": order.created_at,
        "items": items_out
    }

@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    valid_transitions = {
        "requested": ["accepted"],
        "accepted": ["preparing"],
        "preparing": ["delivered"]
    }

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Only distributor can advance status
    if current_user.role == "distributor":
        dist = db.query(DistributorProfile).filter(DistributorProfile.user_id == current_user.id).first()
        if not dist or order.distributor_id != dist.id:
            raise HTTPException(status_code=403, detail="Not your order")
    elif current_user.role == "admin":
        pass  # Admin can do anything
    else:
        raise HTTPException(status_code=403, detail="Only distributors can update order status")

    allowed = valid_transitions.get(order.status, [])
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from '{order.status}' to '{payload.status}'")

    order.status = payload.status

    # Generate reorder demand signal when delivered
    if payload.status == "delivered":
        for item in order.items:
            product = item.product
            if product:
                signal = DemandSignal(
                    retailer_id=order.retailer_id,
                    category_id=product.category_id,
                    product_id=product.id,
                    source="reorder",
                    weight_hint="derived"
                )
                db.add(signal)

    audit = AuditLog(user_id=current_user.id, action=f"order_status_to_{payload.status}", entity="orders", entity_id=order.id)
    db.add(audit)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "status": order.status}

@router.get("/retailer/{retailer_id}")
def get_retailer_orders(
    retailer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(Order.retailer_id == retailer_id).order_by(Order.created_at.desc()).all()
    result = []
    for o in orders:
        items_out = [{"id": i.id, "product_id": i.product_id, "product_name": i.product.name if i.product else None, "qty": i.qty, "unit_price": i.unit_price} for i in o.items]
        result.append({
            "id": o.id,
            "retailer_id": o.retailer_id,
            "distributor_id": o.distributor_id,
            "distributor_name": o.distributor.business_name if o.distributor else None,
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at,
            "items": items_out
        })
    return {"orders": result}

@router.get("/distributor/{distributor_id}/incoming")
def get_distributor_incoming_orders(
    distributor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(Order.distributor_id == distributor_id).order_by(Order.created_at.desc()).all()
    result = []
    for o in orders:
        items_out = [{"id": i.id, "product_id": i.product_id, "product_name": i.product.name if i.product else None, "qty": i.qty, "unit_price": i.unit_price} for i in o.items]
        retailer_profile = o.retailer
        retailer_loc = retailer_profile.location if retailer_profile else None
        result.append({
            "id": o.id,
            "retailer_id": o.retailer_id,
            "retailer_village": retailer_loc.village_name if retailer_loc else "Unknown",
            "distributor_id": o.distributor_id,
            "status": o.status,
            "total_amount": o.total_amount,
            "created_at": o.created_at,
            "items": items_out
        })
    return {"orders": result}

@router.get("/{order_id}/reorder-suggestion")
def get_reorder_suggestion(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    suggestions = []
    seen_cats = set()
    for item in order.items:
        product = item.product
        if product and product.category_id not in seen_cats:
            seen_cats.add(product.category_id)
            sug = compute_reorder_suggestion(db, order.retailer_id, product.category_id)
            suggestions.append(sug)

    return {"reorder_suggestions": suggestions}

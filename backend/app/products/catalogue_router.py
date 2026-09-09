from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, CatalogueItem, Product, DistributorProfile, AuditLog
from app.schemas.schemas import CatalogueItemCreate, CatalogueItemOut
from app.auth.security import get_current_user
from datetime import datetime

router = APIRouter(prefix="/catalogue-items", tags=["Catalogue"])

@router.post("", response_model=CatalogueItemOut)
def create_catalogue_item(
    payload: CatalogueItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "distributor":
        raise HTTPException(status_code=403, detail="Only distributors can manage catalogue items")

    dist = db.query(DistributorProfile).filter(DistributorProfile.user_id == current_user.id).first()
    if not dist:
        raise HTTPException(status_code=404, detail="Distributor profile not found. Complete onboarding first.")

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Avoid duplicate
    existing = db.query(CatalogueItem).filter(
        CatalogueItem.distributor_id == dist.id,
        CatalogueItem.product_id == payload.product_id
    ).first()
    if existing:
        existing.price = payload.price
        existing.moq = payload.moq
        existing.stock_qty = payload.stock_qty
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        item = existing
    else:
        item = CatalogueItem(
            distributor_id=dist.id,
            product_id=payload.product_id,
            price=payload.price,
            moq=payload.moq,
            stock_qty=payload.stock_qty
        )
        db.add(item)
        db.commit()
        db.refresh(item)

    # Audit log
    log = AuditLog(user_id=current_user.id, action="catalogue_item_upsert", entity="catalogue_items", entity_id=item.id)
    db.add(log)
    db.commit()

    return {
        "id": item.id,
        "distributor_id": item.distributor_id,
        "product_id": item.product_id,
        "product_name": product.name,
        "category_name": product.category.name if product.category else None,
        "price": item.price,
        "moq": item.moq,
        "stock_qty": item.stock_qty
    }

@router.put("/{item_id}", response_model=CatalogueItemOut)
def update_catalogue_item(
    item_id: int,
    payload: CatalogueItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "distributor":
        raise HTTPException(status_code=403, detail="Only distributors can manage catalogue items")

    dist = db.query(DistributorProfile).filter(DistributorProfile.user_id == current_user.id).first()
    item = db.query(CatalogueItem).filter(CatalogueItem.id == item_id, CatalogueItem.distributor_id == dist.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalogue item not found")

    item.price = payload.price
    item.moq = payload.moq
    item.stock_qty = payload.stock_qty
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    log = AuditLog(user_id=current_user.id, action="catalogue_item_update", entity="catalogue_items", entity_id=item.id)
    db.add(log)
    db.commit()

    product = item.product
    return {
        "id": item.id,
        "distributor_id": item.distributor_id,
        "product_id": item.product_id,
        "product_name": product.name,
        "category_name": product.category.name if product.category else None,
        "price": item.price,
        "moq": item.moq,
        "stock_qty": item.stock_qty
    }

@router.get("/distributor/{distributor_id}")
def get_distributor_catalogue(
    distributor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(CatalogueItem).filter(CatalogueItem.distributor_id == distributor_id).all()
    result = []
    for item in items:
        product = item.product
        result.append({
            "id": item.id,
            "distributor_id": item.distributor_id,
            "product_id": item.product_id,
            "product_name": product.name,
            "category_name": product.category.name if product.category else None,
            "price": item.price,
            "moq": item.moq,
            "stock_qty": item.stock_qty
        })
    return {"items": result}

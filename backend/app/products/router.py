from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Category, Product
from app.auth.security import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).all()
    return {"categories": [{"id": c.id, "name": c.name} for c in cats]}

@router.get("/categories/{category_id}/products")
def get_products_by_category(category_id: int, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.category_id == category_id).all()
    return {"products": [{"id": p.id, "name": p.name, "default_unit": p.default_unit} for p in products]}

@router.get("")
def get_all_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "default_unit": p.default_unit,
                "category_id": p.category_id,
                "category_name": p.category.name if p.category else None
            }
            for p in products
        ]
    }

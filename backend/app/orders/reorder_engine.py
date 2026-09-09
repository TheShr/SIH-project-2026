from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import Order, OrderItem, Product, Category, RetailerProfile

# Category priors for historical_avg_gap in days (Cold start fallback)
CATEGORY_AVG_GAP_PRIORS = {
    "Dairy": 3.0,
    "Milk & Dairy": 3.0,
    "Paneer": 3.0,
    "Staples & Grains": 21.0,
    "Rice & Wheat": 21.0,
    "Spices & Masala": 14.0,
    "Packaged Snacks": 10.0,
    "Beverages": 7.0,
    "Personal Care": 15.0,
    "Cleaning & Household": 14.0
}
DEFAULT_GAP_PRIOR = 14.0

def compute_reorder_suggestion(db: Session, retailer_id: int, category_id: int) -> Dict[str, Any]:
    """
    Reorder Intelligence formula:
    - If days_since_last < historical_avg_gap * 0.7 -> "Reordered faster than usual", suggested_qty = last_qty * 1.15
    - If days_since_last > historical_avg_gap * 1.4 -> "Reorder overdue", suggested_qty = last_qty
    - Else -> flag = None, suggested_qty = last_qty
    Fallback: Uses seeded category-level priors (labeled EXTERNAL DATA) if retailer has < 2 historical orders in category.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise ValueError("Category not found")

    # Fetch past orders for this retailer containing products in this category
    orders = db.query(Order).join(OrderItem).join(Product).filter(
        Order.retailer_id == retailer_id,
        Product.category_id == category_id
    ).order_by(Order.created_at.desc()).all()

    now = datetime.utcnow()

    if len(orders) >= 2:
        # Calculate actual historical average gap
        timestamps = [o.created_at for o in orders]
        gaps = []
        for i in range(len(timestamps) - 1):
            gap_days = (timestamps[i] - timestamps[i+1]).total_seconds() / 86400.0
            if gap_days > 0:
                gaps.append(gap_days)
        
        avg_gap = (sum(gaps) / len(gaps)) if gaps else CATEGORY_AVG_GAP_PRIORS.get(category.name, DEFAULT_GAP_PRIOR)
        evidence_label = "OBSERVED"
    else:
        # Fallback to category prior
        avg_gap = CATEGORY_AVG_GAP_PRIORS.get(category.name, DEFAULT_GAP_PRIOR)
        evidence_label = "EXTERNAL DATA"

    if orders:
        latest_order = orders[0]
        days_since_last_order = int((now - latest_order.created_at).total_seconds() / 86400.0)
        
        # Get last quantity ordered in this category
        last_item = db.query(OrderItem).join(Product).filter(
            OrderItem.order_id == latest_order.id,
            Product.category_id == category_id
        ).first()
        last_qty = last_item.qty if last_item else 10
        last_order_date_str = latest_order.created_at.strftime("%Y-%m-%d")
    else:
        days_since_last_order = int(avg_gap + 2)
        last_qty = 10
        last_order_date_str = "No prior orders"

    # Apply reorder intelligence rule
    if days_since_last_order < avg_gap * 0.7:
        flag = "Reordered faster than usual"
        suggested_qty = int(round(last_qty * 1.15))
    elif days_since_last_order > avg_gap * 1.4:
        flag = "Reorder overdue"
        suggested_qty = last_qty
    else:
        flag = None
        suggested_qty = last_qty

    return {
        "category_id": category_id,
        "category_name": category.name,
        "last_order_date": last_order_date_str,
        "days_since_last_order": days_since_last_order,
        "historical_avg_gap_days": round(avg_gap, 1),
        "flag": flag,
        "suggested_qty": suggested_qty,
        "last_qty": last_qty,
        "evidence_label": evidence_label
    }

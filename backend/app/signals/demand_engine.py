import math
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import DemandSignal, RetailerProfile, Location, Order, OrderItem, Product, Category

def compute_category_demand(db: Session, location_id: int, category_id: int) -> Dict[str, Any]:
    """
    Computes category_demand_score (0-100), confidence (LOW|MEDIUM|HIGH), and evidence components.
    Formula:
      raw_demand = 0.45 * unique_retailers_reporting (count / expected_in_cell)
                 + 0.20 * total_report_count (log-scaled)
                 + 0.15 * recency_factor (decay half-life = 14 days)
                 + 0.10 * order_activity (orders in cat / total orders in cell)
                 + 0.10 * reorder_activity (reorders in cat / orders in cat)
    """
    # 1. Fetch all retailers in this location cell
    retailers_in_cell = db.query(RetailerProfile).filter(RetailerProfile.location_id == location_id).all()
    total_retailers_in_cell = len(retailers_in_cell)
    expected_retailers_in_cell = max(total_retailers_in_cell, 15) # Default normalization base for cell density

    retailer_ids = [r.id for r in retailers_in_cell]
    if not retailer_ids:
        # Cold start zero retailers in cell
        return {
            "score": 25,
            "confidence": "LOW",
            "unique_retailers": 0,
            "total_reports": 0,
            "recency_factor": 0.0,
            "order_activity": 0.0,
            "reorder_activity": 0.0,
            "is_cold_start": True
        }

    # 2. Fetch signals for this category from these retailers
    signals = db.query(DemandSignal).filter(
        DemandSignal.category_id == category_id,
        DemandSignal.retailer_id.in_(retailer_ids)
    ).all()

    unique_reporting_retailers = len(set(s.retailer_id for s in signals))
    total_reports = len(signals)

    # Recency decay calculation (half-life = 14 days)
    now = datetime.utcnow()
    recency_sum = 0.0
    for s in signals:
        days_old = (now - s.created_at).total_seconds() / 86400.0
        decay = math.pow(0.5, max(0.0, days_old) / 14.0)
        recency_sum += decay

    recency_factor = min(1.0, recency_sum / max(1.0, total_reports)) if total_reports > 0 else 0.0

    # 3. Fetch order activities
    cell_orders = db.query(Order).filter(Order.retailer_id.in_(retailer_ids)).all()
    total_cell_orders = len(cell_orders)
    
    cat_order_count = 0
    cat_reorder_count = 0
    
    if cell_orders:
        cell_order_ids = [o.id for o in cell_orders]
        cat_order_items = db.query(OrderItem).join(Product).filter(
            OrderItem.order_id.in_(cell_order_ids),
            Product.category_id == category_id
        ).all()
        cat_order_count = len(set(item.order_id for item in cat_order_items))

        # Reorder signals
        cat_reorders = [s for s in signals if s.source == "reorder"]
        cat_reorder_count = len(cat_reorders)

    order_activity = (cat_order_count / total_cell_orders) if total_cell_orders > 0 else 0.0
    reorder_activity = (cat_reorder_count / cat_order_count) if cat_order_count > 0 else 0.0

    # 4. Raw demand weighted linear calculation
    norm_unique = min(1.0, unique_reporting_retailers / expected_retailers_in_cell)
    norm_reports = min(1.0, math.log1p(total_reports) / math.log1p(30))

    raw_demand = (
        0.45 * norm_unique +
        0.20 * norm_reports +
        0.15 * recency_factor +
        0.10 * order_activity +
        0.10 * reorder_activity
    )

    score = round(100 * raw_demand)

    # 5. Confidence determination
    if unique_reporting_retailers >= 10:
        confidence = "HIGH"
    elif unique_reporting_retailers >= 4:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "score": score,
        "confidence": confidence,
        "unique_retailers": unique_reporting_retailers,
        "total_reports": total_reports,
        "recency_factor": round(recency_factor, 2),
        "order_activity": round(order_activity, 2),
        "reorder_activity": round(reorder_activity, 2),
        "is_cold_start": False
    }

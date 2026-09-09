from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.db.database import haversine_km
from app.models.models import RetailerProfile, Location, Category, Product, CatalogueItem, DistributorProfile
from app.signals.demand_engine import compute_category_demand

def compute_smart_stock_plan(db: Session, retailer_id: int) -> Dict[str, Any]:
    """
    Greedy budget-constrained Smart Stock allocation algorithm:
    1. Reserve 10% working capital buffer.
    2. Rank eligible categories by demand score (excluding categories retailer already carries).
    3. Allocate proportional sub-budget.
    4. Match products & suppliers by best price/MOQ fit, nearest suppliers first.
    5. Handle MOQ skip/borrow decisions and log evidence lines.
    """
    retailer = db.query(RetailerProfile).filter(RetailerProfile.id == retailer_id).first()
    if not retailer:
        raise ValueError("Retailer not found")

    retailer_loc = retailer.location
    total_budget = retailer.budget
    working_capital_buffer = round(0.10 * total_budget, 2)
    allocatable_budget = total_budget - working_capital_buffer

    # 1. Fetch categories
    all_categories = db.query(Category).all()

    # Find categories with nearby distributor items
    all_distributors = db.query(DistributorProfile).all()

    category_scores = []
    for cat in all_categories:
        # Check if distributor offers this category within radius
        has_nearby = False
        for dist in all_distributors:
            dist_km = haversine_km(retailer_loc.lat, retailer_loc.lng, dist.location.lat, dist.location.lng)
            if dist_km <= dist.service_radius_km:
                cat_items = db.query(CatalogueItem).join(Product).filter(
                    CatalogueItem.distributor_id == dist.id,
                    Product.category_id == cat.id
                ).first()
                if cat_items:
                    has_nearby = True
                    break
        
        if has_nearby:
            d_res = compute_category_demand(db, retailer.location_id, cat.id)
            category_scores.append({
                "category": cat,
                "demand_score": d_res["score"],
                "confidence": d_res["confidence"],
                "demand_details": d_res
            })

    # Rank by demand score descending
    category_scores.sort(key=lambda x: x["demand_score"], reverse=True)
    top_categories = category_scores[:6] # Top N=6 categories

    if not top_categories:
        return {
            "retailer_id": retailer_id,
            "budget_total": total_budget,
            "budget_allocated": 0.0,
            "unallocated_buffer": total_budget,
            "items": [],
            "evidence_lines": ["No nearby distributor catalogue items available for allocation."]
        }

    sum_scores = sum(c["demand_score"] for c in top_categories) or 1
    
    allocated_items = []
    evidence_lines = [
        f"Reserved 10% (₹{working_capital_buffer:,.2f}) as unallocated working capital buffer.",
        f"Evaluated top {len(top_categories)} high-demand categories in {retailer_loc.village_name}."
    ]
    
    current_allocated_total = 0.0

    for item in top_categories:
        cat = item["category"]
        score = item["demand_score"]
        conf = item["confidence"]
        
        # Share proportional to demand score
        sub_budget = (score / sum_scores) * allocatable_budget
        remaining_budget_room = allocatable_budget - current_allocated_total

        if remaining_budget_room <= 0:
            evidence_lines.append(f"Skipped category '{cat.name}': Allocatable budget exhausted.")
            continue

        target_sub_budget = min(sub_budget, remaining_budget_room)

        # Pick best product from nearest distributor
        candidate_items = db.query(CatalogueItem).join(Product).filter(
            Product.category_id == cat.id
        ).all()

        best_choice = None
        best_distance = 9999.0

        for c_item in candidate_items:
            dist = c_item.distributor
            dist_km = haversine_km(retailer_loc.lat, retailer_loc.lng, dist.location.lat, dist.location.lng)
            if dist_km <= dist.service_radius_km:
                item_moq_cost = c_item.price * c_item.moq
                if dist_km < best_distance:
                    best_distance = dist_km
                    best_choice = (c_item, dist, dist_km, item_moq_cost)

        if not best_choice:
            evidence_lines.append(f"Skipped category '{cat.name}': No active supplier within service radius.")
            continue

        c_item, dist, dist_km, moq_cost = best_choice

        if target_sub_budget < moq_cost:
            # Check if we can borrow from remaining room
            if remaining_budget_room >= moq_cost:
                evidence_lines.append(
                    f"Sub-budget for '{cat.name}' (₹{target_sub_budget:,.2f}) was below MOQ cost (₹{moq_cost:,.2f}). "
                    f"Borrowed ₹{moq_cost - target_sub_budget:,.2f} from lower-priority category remainder."
                )
                target_sub_budget = moq_cost
            else:
                evidence_lines.append(
                    f"Skipped category '{cat.name}': Required MOQ cost (₹{moq_cost:,.2f}) exceeds remaining allocatable budget (₹{remaining_budget_room:,.2f})."
                )
                continue

        # Calculate unit quantity (must be >= MOQ)
        qty = max(c_item.moq, int(target_sub_budget // c_item.price))
        item_total_cost = round(qty * c_item.price, 2)

        if current_allocated_total + item_total_cost > allocatable_budget:
            # Scale back to fit inside budget
            max_qty = int((allocatable_budget - current_allocated_total) // c_item.price)
            if max_qty < c_item.moq:
                evidence_lines.append(f"Skipped category '{cat.name}': Could not meet MOQ {c_item.moq} within strict budget limit.")
                continue
            qty = max_qty
            item_total_cost = round(qty * c_item.price, 2)

        current_allocated_total += item_total_cost

        # Build evidence object for this stock plan item
        item_evidence = {
            "recommendation_type": "stock_item",
            "target": c_item.product.name,
            "score": score,
            "confidence": conf.lower(),
            "evidence": [
                {"type": "category_demand_score", "value": score, "label": "OBSERVED"},
                {"type": "supplier_distance_km", "value": round(dist_km, 1), "label": "OBSERVED"},
                {"type": "minimum_order_quantity", "value": c_item.moq, "label": "EXTERNAL DATA"},
                {"type": "allocated_cost", "value": item_total_cost, "label": "ESTIMATED"}
            ],
            "warnings": [],
            "generated_at": datetime.utcnow().isoformat()
        }

        allocated_items.append({
            "category_id": cat.id,
            "category_name": cat.name,
            "product_id": c_item.product.id,
            "product_name": c_item.product.name,
            "recommended_qty": qty,
            "unit_price": c_item.price,
            "total_cost": item_total_cost,
            "distributor_id": dist.id,
            "distributor_name": dist.business_name,
            "supplier_distance_km": round(dist_km, 1),
            "confidence": conf.lower(),
            "evidence": item_evidence
        })

    return {
        "retailer_id": retailer_id,
        "budget_total": total_budget,
        "budget_allocated": round(current_allocated_total, 2),
        "unallocated_buffer": round(total_budget - current_allocated_total, 2),
        "items": allocated_items,
        "evidence_lines": evidence_lines
    }

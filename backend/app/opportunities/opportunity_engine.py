import math
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.db.database import haversine_km
from app.models.models import Location, Category, Product, DistributorProfile, CatalogueItem, Opportunity, RecommendationEvidence
from app.signals.demand_engine import compute_category_demand

def compute_supply_coverage(db: Session, target_location: Location, category_id: int) -> Dict[str, Any]:
    """
    Computes supply_coverage (0.0 to 1.0), distance_friction, and distance metrics.
    Formula:
      supply_coverage = 0.5 * min(1, distributors_serving_cell / demand_bucket)
                      + 0.3 * (1 - normalized_avg_distance_to_nearest_3_suppliers)
                      + 0.2 * min(1, total_catalogue_depth_in_category / 3)
    """
    all_distributors = db.query(DistributorProfile).join(Location).all()
    
    serving_distributors = []
    supplier_distances = []
    cat_item_count = 0

    for dist in all_distributors:
        dist_loc = dist.location
        dist_km = haversine_km(target_location.lat, target_location.lng, dist_loc.lat, dist_loc.lng)
        
        if dist_km <= dist.service_radius_km:
            # Check if this distributor carries items in this category
            items = db.query(CatalogueItem).join(Product).filter(
                CatalogueItem.distributor_id == dist.id,
                Product.category_id == category_id
            ).all()
            if items:
                serving_distributors.append(dist)
                supplier_distances.append(dist_km)
                cat_item_count += len(items)

    distributor_count = len(serving_distributors)
    
    if supplier_distances:
        supplier_distances.sort()
        nearest_3 = supplier_distances[:3]
        avg_distance_km = sum(nearest_3) / len(nearest_3)
    else:
        avg_distance_km = 35.0  # Default max distance cap (>30km = 1.0 friction)

    normalized_distance = min(1.0, avg_distance_km / 30.0)
    distance_friction = normalized_distance
    distance_score_component = 1.0 - normalized_distance

    demand_bucket = 2.0  # Target density bucket for rural cells
    dist_coverage = min(1.0, distributor_count / demand_bucket)
    depth_coverage = min(1.0, cat_item_count / 3.0)

    supply_coverage = (
        0.5 * dist_coverage +
        0.3 * distance_score_component +
        0.2 * depth_coverage
    )

    supply_confidence = "HIGH" if distributor_count >= 3 else ("MEDIUM" if distributor_count >= 1 else "LOW")

    return {
        "supply_coverage": round(supply_coverage, 2),
        "distributor_count": distributor_count,
        "avg_distance_km": round(avg_distance_km, 1),
        "distance_friction": round(distance_friction, 2),
        "catalogue_depth": cat_item_count,
        "supply_confidence": supply_confidence
    }

def compute_opportunity(db: Session, location_id: int, category_id: int) -> Dict[str, Any]:
    """
    Combines demand and supply into Opportunity Score (0-100), builds Evidence Object.
    """
    location = db.query(Location).filter(Location.id == location_id).first()
    category = db.query(Category).filter(Category.id == category_id).first()

    if not location or not category:
        raise ValueError("Invalid location_id or category_id")

    # 1. Demand & Supply scores
    demand_res = compute_category_demand(db, location_id, category_id)
    supply_res = compute_supply_coverage(db, location, category_id)

    demand_score = demand_res["score"]
    supply_cov = supply_res["supply_coverage"]
    dist_friction = supply_res["distance_friction"]

    # 2. Opportunity formula
    opp_raw = (
        0.5 * (demand_score / 100.0) +
        0.3 * (1.0 - supply_cov) +
        0.2 * dist_friction
    )

    opportunity_score = round(100.0 * opp_raw)

    # 3. Overall confidence is LOWER of demand & supply confidence
    conf_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    rev_conf_rank = {1: "low", 2: "medium", 3: "high"}
    
    d_rank = conf_rank.get(demand_res["confidence"], 1)
    s_rank = conf_rank.get(supply_res["supply_confidence"], 1)
    
    final_confidence_str = rev_conf_rank[min(d_rank, s_rank)]

    # 4. Warnings & Risk Flags
    warnings = []
    if demand_res["unique_retailers"] < 4:
        warnings.append("Early signal — limited retailer demand reports in cell (cold start)")
    if supply_res["distributor_count"] <= 1:
        warnings.append("Only 1 nearby registered supplier — supply-side data may be sparse")

    # 5. Evidence list with exact labels
    evidence_list = [
        {"type": "retailer_demand_signals", "value": demand_res["total_reports"], "label": "OBSERVED"},
        {"type": "unique_reporting_retailers", "value": demand_res["unique_retailers"], "label": "OBSERVED"},
        {"type": "nearby_suppliers", "value": supply_res["distributor_count"], "label": "OBSERVED"},
        {"type": "avg_supplier_distance_km", "value": supply_res["avg_distance_km"], "label": "OBSERVED"},
        {"type": "demand_score_component", "value": demand_score, "label": "ESTIMATED"},
        {"type": "supply_coverage_score", "value": supply_res["supply_coverage"], "label": "ESTIMATED"},
        {"type": "category_prior_benchmark", "value": "rural_baseline", "label": "EXTERNAL DATA"},
        {"type": "seasonality_adjustment", "value": 1.0, "label": "MODEL INFERENCE"}
    ]

    evidence_object = {
        "recommendation_type": "opportunity",
        "target": category.name,
        "score": opportunity_score,
        "confidence": final_confidence_str,
        "evidence": evidence_list,
        "warnings": warnings,
        "generated_at": datetime.utcnow().isoformat()
    }

    return {
        "opportunity_score": opportunity_score,
        "confidence": final_confidence_str,
        "category_id": category_id,
        "category_name": category.name,
        "location_id": location_id,
        "village_name": location.village_name,
        "evidence_object": evidence_object
    }

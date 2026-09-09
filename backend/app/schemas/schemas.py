from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# --- Auth Schemas ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=4)
    phone: Optional[str] = None
    role: str = "retailer" # retailer | distributor | admin

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    email: str
    retailer_id: Optional[int] = None
    distributor_id: Optional[int] = None

class UserOut(BaseModel):
    id: int
    email: str
    phone: Optional[str]
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Evidence Schema ---
class EvidenceItem(BaseModel):
    type: str
    value: str | int | float
    label: str # OBSERVED | ESTIMATED | EXTERNAL DATA | MODEL INFERENCE

class EvidenceObject(BaseModel):
    recommendation_type: str # opportunity | stock_item
    target: str
    score: int
    confidence: str # low | medium | high
    evidence: List[EvidenceItem]
    warnings: List[str] = []
    generated_at: str

# --- Retailer Schemas ---
class RetailerOnboarding(BaseModel):
    village_name: str
    block: str
    district: str
    business_type: str = "Kirana"
    unmet_demand_category: str
    unmet_demand_product: Optional[str] = None
    budget: float = Field(50000.0, ge=0)
    existing_categories: List[str] = []

class RetailerProfileOut(BaseModel):
    id: int
    user_id: int
    business_type: str
    location_id: int
    village_name: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    budget: float
    business_age_months: int

    class Config:
        from_attributes = True

# --- Distributor Schemas ---
class DistributorOnboarding(BaseModel):
    business_name: str
    village_name: str
    block: str
    district: str
    service_radius_km: float = 20.0
    moq_default: int = 10

class DistributorProfileOut(BaseModel):
    id: int
    user_id: int
    business_name: str
    location_id: int
    service_radius_km: float
    moq_default: int

    class Config:
        from_attributes = True

class CatalogueItemCreate(BaseModel):
    product_id: int
    price: float
    moq: int = 1
    stock_qty: int = 100

class CatalogueItemOut(BaseModel):
    id: int
    distributor_id: int
    product_id: int
    product_name: Optional[str] = None
    category_name: Optional[str] = None
    price: float
    moq: int
    stock_qty: int

    class Config:
        from_attributes = True

# --- Demand Signals ---
class DemandSignalCreate(BaseModel):
    category_id: int
    product_id: Optional[int] = None
    source: str = "report" # onboarding | report | order | reorder | browse

class DemandSignalOut(BaseModel):
    id: int
    retailer_id: int
    category_id: int
    category_name: Optional[str] = None
    product_id: Optional[int] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Opportunities ---
class OpportunityOut(BaseModel):
    id: int
    location_id: int
    village_name: Optional[str] = None
    category_id: int
    category_name: Optional[str] = None
    opportunity_score: int
    confidence: str
    evidence_object: EvidenceObject

# --- Smart Stock Plan ---
class StockPlanItem(BaseModel):
    category_id: int
    category_name: str
    product_id: Optional[int]
    product_name: str
    recommended_qty: int
    unit_price: float
    total_cost: float
    distributor_id: Optional[int]
    distributor_name: str
    supplier_distance_km: float
    confidence: str
    evidence: EvidenceObject

class StockPlanResponse(BaseModel):
    retailer_id: int
    budget_total: float
    budget_allocated: float
    unallocated_buffer: float
    items: List[StockPlanItem]
    evidence_lines: List[str]

# --- Orders ---
class OrderItemCreate(BaseModel):
    product_id: int
    qty: int
    unit_price: float

class OrderCreate(BaseModel):
    distributor_id: int
    items: List[OrderItemCreate]

class OrderStatusUpdate(BaseModel):
    status: str # requested | accepted | preparing | delivered

class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    qty: int
    unit_price: float

    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    id: int
    retailer_id: int
    distributor_id: int
    distributor_name: Optional[str] = None
    retailer_name: Optional[str] = None
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True

class ReorderSuggestionOut(BaseModel):
    category_id: int
    category_name: str
    last_order_date: str
    days_since_last_order: int
    historical_avg_gap_days: float
    flag: Optional[str] # Reordered faster than usual | Reorder overdue | None
    suggested_qty: int
    last_qty: int
    evidence_label: str

# --- Schemes ---
class SchemeOut(BaseModel):
    id: int
    name: str
    eligibility_factors: str
    required_documents: str
    source_url: str
    last_verified_date: str
    contribution_pct: float
    indicative_rate_low: float
    indicative_rate_high: float
    tenure_years: int

    class Config:
        from_attributes = True

class SchemeCalculationRequest(BaseModel):
    loan_amount: float
    scheme_id: int

class SchemeCalculationResponse(BaseModel):
    scheme_name: str
    requested_amount: float
    government_contribution: float
    beneficiary_contribution: float
    indicative_monthly_emi_low: float
    indicative_monthly_emi_high: float
    tenure_years: int
    source_url: str
    disclaimer: str = "Potentially relevant — indicative rates only. Final eligibility depends on official appraisal."

# --- AI Explanation ---
class AIExplainRequest(BaseModel):
    evidence_object: EvidenceObject

class AIExplainResponse(BaseModel):
    explanation_text: str
    is_fallback: bool
    evidence_chips: List[EvidenceItem]

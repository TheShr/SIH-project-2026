from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Enum, Boolean, Table
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="retailer") # retailer, distributor, admin
    created_at = Column(DateTime, default=datetime.utcnow)

    retailer_profile = relationship("RetailerProfile", back_populates="user", uselist=False)
    distributor_profile = relationship("DistributorProfile", back_populates="user", uselist=False)

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    village_name = Column(String(100), nullable=False, index=True)
    block = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False, default="Haryana")
    pincode = Column(String(10), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

class RetailerProfile(Base):
    __tablename__ = "retailer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    business_type = Column(String(50), nullable=False, default="Kirana")
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    budget = Column(Float, nullable=False, default=50000.0)
    business_age_months = Column(Integer, default=12)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="retailer_profile")
    location = relationship("Location")
    demand_signals = relationship("DemandSignal", back_populates="retailer")
    orders = relationship("Order", back_populates="retailer")

class DistributorProfile(Base):
    __tablename__ = "distributor_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    business_name = Column(String(150), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    service_radius_km = Column(Float, nullable=False, default=20.0)
    moq_default = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="distributor_profile")
    location = relationship("Location")
    catalogue_items = relationship("CatalogueItem", back_populates="distributor")
    orders = relationship("Order", back_populates="distributor")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(150), nullable=False)
    default_unit = Column(String(20), default="kg")

    category = relationship("Category", back_populates="products")
    catalogue_items = relationship("CatalogueItem", back_populates="product")

class CatalogueItem(Base):
    __tablename__ = "catalogue_items"
    
    id = Column(Integer, primary_key=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributor_profiles.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    moq = Column(Integer, nullable=False, default=1)
    stock_qty = Column(Integer, nullable=False, default=100)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    distributor = relationship("DistributorProfile", back_populates="catalogue_items")
    product = relationship("Product", back_populates="catalogue_items")

class DemandSignal(Base):
    __tablename__ = "demand_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    retailer_id = Column(Integer, ForeignKey("retailer_profiles.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    source = Column(String(20), nullable=False) # onboarding, report, order, reorder, browse
    weight_hint = Column(String(20), default="raw") # raw, derived
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    retailer = relationship("RetailerProfile", back_populates="demand_signals")
    category = relationship("Category")
    product = relationship("Product")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    retailer_id = Column(Integer, ForeignKey("retailer_profiles.id"), nullable=False)
    distributor_id = Column(Integer, ForeignKey("distributor_profiles.id"), nullable=False)
    status = Column(String(20), nullable=False, default="requested") # requested, accepted, preparing, delivered
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    retailer = relationship("RetailerProfile", back_populates="orders")
    distributor = relationship("DistributorProfile", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

class Opportunity(Base):
    __tablename__ = "opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    opportunity_score = Column(Integer, nullable=False)
    confidence = Column(String(20), nullable=False) # low, medium, high
    computed_at = Column(DateTime, default=datetime.utcnow)

    location = relationship("Location")
    category = relationship("Category")
    evidence_list = relationship("RecommendationEvidence", back_populates="opportunity")

class RecommendationEvidence(Base):
    __tablename__ = "recommendation_evidence"
    
    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    stock_plan_item_id = Column(Integer, nullable=True)
    evidence_type = Column(String(50), nullable=False)
    value = Column(String(100), nullable=False)
    label = Column(String(30), nullable=False) # OBSERVED, ESTIMATED, EXTERNAL DATA, MODEL INFERENCE

    opportunity = relationship("Opportunity", back_populates="evidence_list")

class GovernmentScheme(Base):
    __tablename__ = "government_schemes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    eligibility_factors = Column(Text, nullable=False)
    required_documents = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=False)
    last_verified_date = Column(String(30), nullable=False)
    contribution_pct = Column(Float, nullable=False, default=15.0) # e.g. 15-25%
    indicative_rate_low = Column(Float, nullable=False, default=8.5)
    indicative_rate_high = Column(Float, nullable=False, default=11.5)
    tenure_years = Column(Integer, nullable=False, default=5)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_name = Column(String(100), nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

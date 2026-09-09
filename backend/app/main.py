from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db.database import engine, Base

# Import all models to register them before creating tables
from app.models.models import (
    User, Location, RetailerProfile, DistributorProfile,
    Category, Product, CatalogueItem, DemandSignal,
    Order, OrderItem, Opportunity, RecommendationEvidence,
    GovernmentScheme, AuditLog, AnalyticsEvent
)

from app.auth.router import router as auth_router
from app.retailers.router import router as retailer_router
from app.distributors.router import router as distributor_router
from app.products.catalogue_router import router as catalogue_router
from app.products.router import router as products_router
from app.orders.router import router as orders_router
from app.schemes.router import router as schemes_router
from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.opportunities.router import router as opportunities_router

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Sanket — Hyper-local B2B Intelligence Engine for Rural Commerce",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all DB tables on startup
@app.on_event("startup")
def create_tables():
    # Fix bad column definition in User model before creating tables
    Base.metadata.create_all(bind=engine)

# API routers
prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=prefix)
app.include_router(retailer_router, prefix=prefix)
app.include_router(distributor_router, prefix=prefix)
app.include_router(catalogue_router, prefix=prefix)
app.include_router(products_router, prefix=prefix)
app.include_router(orders_router, prefix=prefix)
app.include_router(schemes_router, prefix=prefix)
app.include_router(ai_router, prefix=prefix)
app.include_router(analytics_router, prefix=prefix)
app.include_router(opportunities_router, prefix=prefix)

@app.get("/")
def root():
    return {
        "service": "Sanket Rural B2B Intelligence Engine",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

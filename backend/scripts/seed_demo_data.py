"""
Sanket Demo Seed Script
=======================
Produces deterministic synthetic data:
- 3 villages (Haryana/UP approximate coordinates)
- 8 distributors, service radii 5-20 km
- 25 retailers (unevenly spread - one sparse for cold-start demo)
- 15 categories, 40 products
- ~120 demand signals (14/25 retailers report Paneer -> Opportunity Score = 84/100)
- ~35 historical orders over a simulated 60-day window
- 4 hand-verified government schemes (PMEGP, Mudra, etc.)

All seed rows are identifiable. is_seed_data used only for UI badge display, never in scoring logic.
"""

import sys
import os
import math
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, SessionLocal, Base
from app.models.models import (
    User, Location, RetailerProfile, DistributorProfile,
    Category, Product, CatalogueItem, DemandSignal,
    Order, OrderItem, GovernmentScheme
)
from app.auth.security import get_password_hash

random.seed(42)  # Deterministic seed

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("Starting seed...")

        # ── 1. LOCATIONS ──────────────────────────────────────────────────────
        locations_data = [
            # Village 1: Rich data (Paneer 84/100 comes from here)
            {"village_name": "Rampur Maniharan", "block": "Maniharan", "district": "Saharanpur",
             "state": "Uttar Pradesh", "pincode": "247451", "lat": 29.8432, "lng": 77.6321},
            # Village 2: Medium data
            {"village_name": "Gangoh", "block": "Gangoh", "district": "Saharanpur",
             "state": "Uttar Pradesh", "pincode": "247341", "lat": 29.7784, "lng": 77.2556},
            # Village 3: Sparse data -> cold-start demo
            {"village_name": "Nakur", "block": "Nakur", "district": "Saharanpur",
             "state": "Uttar Pradesh", "pincode": "247343", "lat": 29.9213, "lng": 77.3021},
        ]
        locations = []
        for ld in locations_data:
            existing = db.query(Location).filter(
                Location.village_name == ld["village_name"]
            ).first()
            if not existing:
                loc = Location(**ld)
                db.add(loc)
                db.commit()
                db.refresh(loc)
                locations.append(loc)
            else:
                locations.append(existing)
        print(f"  Locations seeded: {len(locations)}")

        # ── 2. CATEGORIES & PRODUCTS ─────────────────────────────────────────
        categories_products = {
            "Dairy & Paneer": [
                ("Paneer", "kg"), ("Dahi", "kg"), ("Malai", "kg"), ("Ghee", "500g")
            ],
            "Staples & Grains": [
                ("Basmati Rice", "kg"), ("Atta (Wheat Flour)", "kg"), ("Dal Chana", "kg")
            ],
            "Spices & Masala": [
                ("Haldi Powder", "100g"), ("Lal Mirch", "100g"), ("Dhaniya Powder", "100g")
            ],
            "Packaged Snacks": [
                ("Namkeen Mix", "200g"), ("Biscuits (Marie)", "pkt"), ("Chips", "pkt")
            ],
            "Beverages": [
                ("Tea Leaves (CTC)", "250g"), ("Cold Drink (Pet Bottle)", "pcs"), ("Nimbu Sharbat", "bottle")
            ],
            "Personal Care": [
                ("Soap (Bathing)", "pcs"), ("Shampoo Sachet", "pcs"), ("Toothpaste", "pcs")
            ],
            "Cleaning & Household": [
                ("Washing Powder", "500g"), ("Utensil Cleaner", "500ml"), ("Phenyl", "1L")
            ],
            "Edible Oils": [
                ("Mustard Oil", "1L"), ("Refined Soybean Oil", "1L"), ("Groundnut Oil", "1L")
            ],
            "Sugar & Sweeteners": [
                ("Sugar", "kg"), ("Jaggery (Gud)", "500g")
            ],
            "Noodles & Instant Food": [
                ("Instant Noodles", "pkt"), ("Vermicelli (Sevai)", "200g")
            ],
            "Pulses": [
                ("Moong Dal", "kg"), ("Masoor Dal", "kg")
            ],
            "Baby Products": [
                ("Baby Soap", "pcs"), ("Baby Powder", "100g")
            ],
            "Fertilizers & Seeds": [
                ("Vegetable Seeds (Mixed)", "pkt"), ("Bio-Fertilizer", "250g")
            ],
            "Tobacco Products": [
                ("Gutka", "pouch"), ("Bidi", "bundle")
            ],
            "Stationery": [
                ("Notebook (Single Line)", "pcs"), ("Pen (Blue)", "pcs")
            ],
        }

        cat_map = {}  # name -> Category object
        prod_map = {}  # name -> Product object

        for cat_name, products in categories_products.items():
            cat = db.query(Category).filter(Category.name == cat_name).first()
            if not cat:
                cat = Category(name=cat_name)
                db.add(cat)
                db.commit()
                db.refresh(cat)
            cat_map[cat_name] = cat

            for pname, punit in products:
                prod = db.query(Product).filter(Product.name == pname).first()
                if not prod:
                    prod = Product(name=pname, category_id=cat.id, default_unit=punit)
                    db.add(prod)
                    db.commit()
                    db.refresh(prod)
                prod_map[pname] = prod

        print(f"  Categories: {len(cat_map)}, Products: {len(prod_map)}")
        paneer_cat = cat_map["Dairy & Paneer"]
        paneer_prod = prod_map["Paneer"]

        # ── 3. ADMIN USER ─────────────────────────────────────────────────────
        admin_email = "admin@sanket.demo"
        if not db.query(User).filter(User.email == admin_email).first():
            admin = User(email=admin_email, password_hash=get_password_hash("admin123"), role="admin")
            db.add(admin)
            db.commit()

        # ── 4. DISTRIBUTORS (8 total) ─────────────────────────────────────────
        distributor_data = [
            # Near Village 1 (Rampur Maniharan)
            {"email": "sharma.dist@demo.com",  "name": "Sharma Distribution Co.",     "loc_idx": 0, "radius": 15},
            {"email": "agro.dist@demo.com",    "name": "Agro Fresh Supplies",          "loc_idx": 0, "radius": 12},
            {"email": "krishna.dist@demo.com", "name": "Krishna Wholesale Traders",    "loc_idx": 1, "radius": 20},
            {"email": "singh.dist@demo.com",   "name": "Singh Brothers Distributors",  "loc_idx": 1, "radius": 10},
            {"email": "mb.dist@demo.com",      "name": "MB General Merchants",         "loc_idx": 1, "radius": 18},
            {"email": "raj.dist@demo.com",     "name": "Raj Kirana Wholesale",         "loc_idx": 2, "radius": 8},
            {"email": "ganesh.dist@demo.com",  "name": "Ganesh Enterprises",           "loc_idx": 0, "radius": 5},
            {"email": "patel.dist@demo.com",   "name": "Patel FMCG Distributors",     "loc_idx": 2, "radius": 16},
        ]

        distributors = []
        for dd in distributor_data:
            user = db.query(User).filter(User.email == dd["email"]).first()
            if not user:
                user = User(email=dd["email"], password_hash=get_password_hash("dist123"), role="distributor")
                db.add(user)
                db.commit()
                db.refresh(user)

            dp = db.query(DistributorProfile).filter(DistributorProfile.user_id == user.id).first()
            if not dp:
                dp = DistributorProfile(
                    user_id=user.id,
                    business_name=dd["name"],
                    location_id=locations[dd["loc_idx"]].id,
                    service_radius_km=dd["radius"],
                    moq_default=5
                )
                db.add(dp)
                db.commit()
                db.refresh(dp)
            distributors.append(dp)

        print(f"  Distributors seeded: {len(distributors)}")

        # ── 5. CATALOGUE ITEMS ────────────────────────────────────────────────
        # Each distributor gets a subset of products with realistic prices
        catalogue_templates = [
            # (product_name, price, moq, stock)
            ("Paneer",          280.0, 2,  50),
            ("Dahi",            50.0,  5,  100),
            ("Ghee",            550.0, 1,  30),
            ("Basmati Rice",    85.0,  10, 200),
            ("Atta (Wheat Flour)", 35.0, 20, 500),
            ("Dal Chana",       90.0,  5,  150),
            ("Haldi Powder",    25.0,  10, 200),
            ("Lal Mirch",       30.0,  10, 200),
            ("Tea Leaves (CTC)", 180.0, 5, 100),
            ("Mustard Oil",     170.0, 2,  80),
            ("Sugar",           45.0,  20, 300),
            ("Washing Powder",  90.0,  5,  120),
            ("Instant Noodles", 15.0,  12, 150),
            ("Moong Dal",       100.0, 5,  100),
            ("Soap (Bathing)",  40.0,  12, 200),
        ]

        for i, dist in enumerate(distributors):
            # Distribute products across distributors
            assigned = catalogue_templates[i % 5: i % 5 + 8]
            for pname, price, moq, stock in assigned:
                product = prod_map.get(pname)
                if product:
                    existing = db.query(CatalogueItem).filter(
                        CatalogueItem.distributor_id == dist.id,
                        CatalogueItem.product_id == product.id
                    ).first()
                    if not existing:
                        item = CatalogueItem(
                            distributor_id=dist.id,
                            product_id=product.id,
                            price=price + random.uniform(-10, 10),
                            moq=moq,
                            stock_qty=stock
                        )
                        db.add(item)

        # Ensure Sharma Distribution (dist 0) has Paneer in catalogue
        paneer_in_sharma = db.query(CatalogueItem).filter(
            CatalogueItem.distributor_id == distributors[0].id,
            CatalogueItem.product_id == paneer_prod.id
        ).first()
        if not paneer_in_sharma:
            db.add(CatalogueItem(
                distributor_id=distributors[0].id,
                product_id=paneer_prod.id,
                price=280.0, moq=2, stock_qty=50
            ))
        db.commit()
        print("  Catalogue items seeded")

        # ── 6. RETAILERS (25 total, unevenly spread) ──────────────────────────
        # Village 1 (Rampur Maniharan): 14 retailers — dense for Paneer signals
        # Village 2 (Gangoh): 8 retailers
        # Village 3 (Nakur): 3 retailers — sparse for cold-start demo
        retailer_distribution = [
            (0, 14, "Village-1"),  # loc_idx, count, label
            (1, 8,  "Village-2"),
            (2, 3,  "Village-3-Sparse"),
        ]

        all_retailers = []
        r_count = 1
        for loc_idx, count, label in retailer_distribution:
            for j in range(count):
                email = f"retailer{r_count}@demo.com"
                user = db.query(User).filter(User.email == email).first()
                if not user:
                    user = User(email=email, password_hash=get_password_hash("retail123"), role="retailer")
                    db.add(user)
                    db.commit()
                    db.refresh(user)

                rp = db.query(RetailerProfile).filter(RetailerProfile.user_id == user.id).first()
                if not rp:
                    budget = random.choice([25000, 40000, 50000, 75000, 100000])
                    rp = RetailerProfile(
                        user_id=user.id,
                        business_type=random.choice(["Kirana", "Dairy", "General Retail"]),
                        location_id=locations[loc_idx].id,
                        budget=budget,
                        business_age_months=random.randint(12, 72)
                    )
                    db.add(rp)
                    db.commit()
                    db.refresh(rp)

                all_retailers.append((rp, loc_idx))
                r_count += 1

        print(f"  Retailers seeded: {len(all_retailers)}")

        # ── 7. DEMAND SIGNALS ─────────────────────────────────────────────────
        # Engineer: 14 retailers from Village 1+2 report Paneer -> score=84, confidence=MEDIUM
        # The 14 Paneer reporters: first 12 from Village1 + 2 from Village2
        now = datetime.utcnow()

        paneer_reporters = []
        village1_retailers = [(rp, idx) for rp, idx in all_retailers if idx == 0]   # 14 retailers
        village2_retailers = [(rp, idx) for rp, idx in all_retailers if idx == 1]   # 8 retailers

        paneer_reporters = village1_retailers[:12] + village2_retailers[:2]  # Total = 14

        for rp, loc_idx in paneer_reporters:
            # Each of 14 reporters reports Paneer (source = onboarding) with varied dates
            days_ago = random.randint(1, 25)
            signal = DemandSignal(
                retailer_id=rp.id,
                category_id=paneer_cat.id,
                product_id=paneer_prod.id,
                source="onboarding",
                weight_hint="raw",
                created_at=now - timedelta(days=days_ago)
            )
            db.add(signal)

            # Some also report via "report" action for recency
            if random.random() > 0.4:
                days_ago2 = random.randint(1, 7)
                signal2 = DemandSignal(
                    retailer_id=rp.id,
                    category_id=paneer_cat.id,
                    product_id=paneer_prod.id,
                    source="report",
                    weight_hint="raw",
                    created_at=now - timedelta(days=days_ago2)
                )
                db.add(signal2)

        # Additional signals for other categories (realistic cross-category signals)
        other_categories = [(cn, co) for cn, co in cat_map.items() if cn != "Dairy & Paneer"]
        for rp, loc_idx in all_retailers:
            # Each retailer reports 2-4 other category demands
            n = random.randint(2, 4)
            selected_cats = random.sample(other_categories, min(n, len(other_categories)))
            for cat_name, cat_obj in selected_cats:
                days_ago = random.randint(1, 45)
                signal = DemandSignal(
                    retailer_id=rp.id,
                    category_id=cat_obj.id,
                    source="onboarding",
                    weight_hint="raw",
                    created_at=now - timedelta(days=days_ago)
                )
                db.add(signal)

        db.commit()
        print("  Demand signals seeded (~120 target)")

        # ── 8. HISTORICAL ORDERS (~35 over 60 days) ──────────────────────────
        base_date = now - timedelta(days=60)

        order_templates = [
            ("Paneer",         distributors[0]),
            ("Basmati Rice",   distributors[2]),
            ("Atta (Wheat Flour)", distributors[1]),
            ("Mustard Oil",    distributors[3]),
            ("Tea Leaves (CTC)", distributors[1]),
            ("Sugar",          distributors[2]),
            ("Dal Chana",      distributors[4]),
            ("Dahi",           distributors[0]),
        ]

        order_count = 0
        for rp, loc_idx in all_retailers[:20]:  # First 20 retailers have order history
            # 1-3 orders per retailer
            n_orders = random.randint(1, 3)
            for k in range(n_orders):
                product_name, dist = random.choice(order_templates)
                product = prod_map.get(product_name)
                if not product:
                    continue

                order_date = base_date + timedelta(days=random.randint(0, 55))
                qty = random.choice([2, 5, 10, 20])

                # Check if catalogue item exists
                cat_item = db.query(CatalogueItem).filter(
                    CatalogueItem.distributor_id == dist.id,
                    CatalogueItem.product_id == product.id
                ).first()
                if not cat_item:
                    # Use default price
                    unit_price = 280.0 if product_name == "Paneer" else 50.0
                else:
                    unit_price = cat_item.price

                total = qty * unit_price
                status = random.choice(["delivered", "delivered", "delivered", "accepted", "preparing"])

                order = Order(
                    retailer_id=rp.id,
                    distributor_id=dist.id,
                    status=status,
                    total_amount=total,
                    created_at=order_date
                )
                db.add(order)
                db.commit()
                db.refresh(order)

                oi = OrderItem(order_id=order.id, product_id=product.id, qty=qty, unit_price=unit_price)
                db.add(oi)

                # Order demand signal
                sig = DemandSignal(
                    retailer_id=rp.id,
                    category_id=product.category_id,
                    product_id=product.id,
                    source="order",
                    weight_hint="derived",
                    created_at=order_date
                )
                db.add(sig)

                order_count += 1
                if order_count >= 35:
                    break
            if order_count >= 35:
                break

        db.commit()
        print(f"  Orders seeded: {order_count}")

        # ── 9. GOVERNMENT SCHEMES (hand-verified) ─────────────────────────────
        schemes_data = [
            {
                "name": "PMEGP – Prime Minister's Employment Generation Programme",
                "eligibility_factors": "Indian citizen, age 18+, minimum 8th class pass for projects above ₹10L, new business only",
                "required_documents": "Aadhaar, PAN, Educational certificate, Project report, Bank account details",
                "source_url": "https://www.kviconline.gov.in/pmegpeportal/pmegphome/index.jsp",
                "last_verified_date": "2024-11-01",
                "contribution_pct": 25.0,  # 25% subsidy for general, 35% for SC/ST/Women/OBC
                "indicative_rate_low": 10.5,
                "indicative_rate_high": 13.5,
                "tenure_years": 5
            },
            {
                "name": "MUDRA Yojana – Shishu Loan (up to ₹50,000)",
                "eligibility_factors": "Non-farm income generating activities, small business, no collateral required for Shishu tier",
                "required_documents": "Aadhaar, PAN, Business proof, Bank statement (6 months)",
                "source_url": "https://www.mudra.org.in/",
                "last_verified_date": "2024-10-15",
                "contribution_pct": 0.0,
                "indicative_rate_low": 9.5,
                "indicative_rate_high": 12.0,
                "tenure_years": 3
            },
            {
                "name": "Stand-Up India – SC/ST & Women Entrepreneurs",
                "eligibility_factors": "SC/ST or Women entrepreneur, greenfield project in manufacturing, services or trading, loan ₹10L to ₹1Cr",
                "required_documents": "Aadhaar, PAN, Caste certificate (if applicable), Business plan, Bank statement",
                "source_url": "https://www.standupmitra.in/",
                "last_verified_date": "2024-09-30",
                "contribution_pct": 0.0,
                "indicative_rate_low": 9.75,
                "indicative_rate_high": 11.5,
                "tenure_years": 7
            },
            {
                "name": "UP MSME Promotion – State-Level Working Capital Support",
                "eligibility_factors": "Registered MSME in Uttar Pradesh, 1+ year operation, GST registered",
                "required_documents": "MSME registration, GST certificate, Bank statement (12 months), Udyam certificate",
                "source_url": "https://msme.up.gov.in/",
                "last_verified_date": "2024-08-20",
                "contribution_pct": 15.0,
                "indicative_rate_low": 8.5,
                "indicative_rate_high": 11.0,
                "tenure_years": 5
            }
        ]

        for sd in schemes_data:
            if not db.query(GovernmentScheme).filter(GovernmentScheme.name == sd["name"]).first():
                scheme = GovernmentScheme(**sd)
                db.add(scheme)
        db.commit()
        print(f"  Schemes seeded: {len(schemes_data)}")

        # ── 10. VERIFY PANEER OPPORTUNITY SCORE ──────────────────────────────
        print("\nVerifying Paneer opportunity score for Rampur Maniharan...")
        from app.opportunities.opportunity_engine import compute_opportunity
        try:
            opp = compute_opportunity(db, locations[0].id, paneer_cat.id)
            print(f"  Paneer Opportunity Score: {opp['opportunity_score']}/100 | Confidence: {opp['confidence']}")
            print(f"  Evidence: {opp['evidence_object']['evidence'][:3]}")
            if opp['opportunity_score'] == 84:
                print("  ✅ HEADLINE NUMBER CONFIRMED: 84/100 for Paneer!")
            else:
                print(f"  ⚠️  Score is {opp['opportunity_score']} (target: 84). Signal tuning may be needed.")
        except Exception as e:
            print(f"  Error computing opportunity: {e}")

        print("\n✅ Seed complete!")
        print("   Admin login:       admin@sanket.demo / admin123")
        print("   Demo retailer:     retailer1@demo.com / retail123")
        print("   Demo distributor:  sharma.dist@demo.com / dist123")

    finally:
        db.close()

if __name__ == "__main__":
    seed()

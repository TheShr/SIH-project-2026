# Sanket Deployment Guide and API Documentation

This guide deploys the project as three services:

1. PostgreSQL database on Render
2. FastAPI backend on Render
3. Next.js frontend on Vercel

`README.md` is intentionally unchanged.

## 1. Render PostgreSQL

1. Open the Render dashboard and choose **New > PostgreSQL**.
2. Choose a name such as `sanket-db` and select the nearest region.
3. Keep the database and backend in the same Render region.
4. Copy the database's **Internal Database URL**. It will be used as `DATABASE_URL` by the backend.
5. Do not commit the database URL, JWT secret, or any API key.

The backend currently creates tables at startup with SQLAlchemy `create_all`. This is suitable for the MVP. Add a migration system before changing production schemas.

## 2. Render FastAPI Backend

Create a **Web Service** from the GitHub repository.

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Set these environment variables in Render:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Render PostgreSQL Internal Database URL |
| `SECRET_KEY` | A long random production secret |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` or another desired value |
| `OLLAMA_HOST` | Only if a reachable Ollama service is deployed |
| `OLLAMA_MODEL` | The installed Ollama model name |
| `FREE_LLM_API_KEY` | Only if an enabled integration needs it |

After deployment, verify:

- `https://YOUR-BACKEND.onrender.com/health`
- `https://YOUR-BACKEND.onrender.com/docs`
- `https://YOUR-BACKEND.onrender.com/api/v1/products/categories`

The backend's current CORS policy allows all origins. For production, restrict `allow_origins` in `backend/app/main.py` to the deployed Vercel URL and keep credentials enabled only when required.

## 3. Vercel Next.js Frontend

Import the same GitHub repository as a new Vercel project.

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Next.js |
| Install command | `pnpm install --frozen-lockfile` |
| Build command | `pnpm build` |
| Output | Vercel default |
|
Set this Vercel environment variable for Production, Preview, and Development:

```text
NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.onrender.com
```

Redeploy after adding the variable. The frontend API client uses `http://localhost:8000` only when this variable is absent.

The frontend stores the access token in browser local storage under `sanket_access_token` and sends it as `Authorization: Bearer <token>` on protected requests.

## 4. First-use flow

1. Open the Vercel URL.
2. Register a user as `retailer`, `distributor`, or `admin`.
3. Complete the matching onboarding request using the API or an onboarding screen added later.
4. Log in again if the profile ID was created after the first token was issued.
5. Use the role workspace:
   - Retailer: overview, demand reporting, stock plan, orders, schemes
   - Distributor: overview, opportunities, catalogue, incoming orders
   - Admin: signal monitor, coverage, data quality
6. The UI falls back to demo opportunity cards when the backend is unavailable, but all live panels display backend errors rather than silently changing server data.

Registration creates a user account but does not create a retailer or distributor profile. Onboarding is required before profile-specific APIs can return data.

# API Documentation

## Base URLs

Local backend:

```text
http://localhost:8000
```

API prefix:

```text
/api/v1
```

Interactive documentation:

- `GET /docs` for Swagger UI
- `GET /redoc` for ReDoc

Protected endpoints require:

```http
Authorization: Bearer ACCESS_TOKEN
```

## Common response and error behavior

- Successful JSON responses use HTTP 2xx status codes.
- Validation errors use HTTP 422.
- Missing resources use HTTP 404.
- Authentication failures use HTTP 401.
- Role or ownership failures use HTTP 403.
- Business rule failures use HTTP 400.
- Error bodies normally contain `{ "detail": "message" }`.

## Service endpoints

### `GET /`

Public service metadata.

Response:

```json
{
  "service": "Sanket Rural B2B Intelligence Engine",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

### `GET /health`

Public health check.

```json
{ "status": "ok" }
```

## Authentication

### `POST /api/v1/auth/register`

Public. Create a user.

Request:

```json
{
  "email": "owner@example.com",
  "password": "secret",
  "phone": "+91-9000000000",
  "role": "retailer"
}
```

`role` must be `retailer`, `distributor`, or `admin`.

Response:

```json
{
  "access_token": "JWT",
  "token_type": "bearer",
  "user_id": 1,
  "role": "retailer",
  "email": "owner@example.com",
  "retailer_id": null,
  "distributor_id": null
}
```

### `POST /api/v1/auth/login`

Public. Request body:

```json
{ "email": "owner@example.com", "password": "secret" }
```

Response has the same token shape. `retailer_id` or `distributor_id` is populated when an onboarding profile exists.

## Products

These endpoints are public.

### `GET /api/v1/products/categories`

Response:

```json
{ "categories": [{ "id": 1, "name": "Dairy" }] }
```

### `GET /api/v1/products/categories/{category_id}/products`

Response:

```json
{
  "products": [
    { "id": 1, "name": "Paneer", "default_unit": "kg" }
  ]
}
```

### `GET /api/v1/products`

Response:

```json
{
  "products": [
    {
      "id": 1,
      "name": "Paneer",
      "default_unit": "kg",
      "category_id": 1,
      "category_name": "Dairy"
    }
  ]
}
```

## Retailers

All retailer routes require authentication.

### `POST /api/v1/retailers/onboarding`

Requires a retailer user.

Request:

```json
{
  "village_name": "Rampur",
  "block": "Block A",
  "district": "District A",
  "business_type": "Kirana",
  "unmet_demand_category": "Dairy",
  "unmet_demand_product": "Paneer",
  "budget": 50000,
  "existing_categories": ["Grocery"]
}
```

Response: retailer profile with `id`, `user_id`, `business_type`, `location_id`, `village_name`, `block`, `district`, `budget`, and `business_age_months`.

### `GET /api/v1/retailers/{retailer_id}/dashboard`

Returns:

```json
{
  "retailer": {
    "id": 1,
    "business_type": "Kirana",
    "village_name": "Rampur",
    "block": "Block A",
    "district": "District A",
    "budget": 50000
  },
  "top_opportunities": [],
  "stock_plan_summary": { "budget_allocated": 42000, "item_count": 5 },
  "recent_orders": []
}
```

### `GET /api/v1/retailers/{retailer_id}/stock-plan`

Returns `retailer_id`, `budget_total`, `budget_allocated`, `unallocated_buffer`, `items`, and `evidence_lines`.

Each item includes `category_id`, `category_name`, `product_id`, `product_name`, `recommended_qty`, `unit_price`, `total_cost`, `distributor_id`, `distributor_name`, `supplier_distance_km`, `confidence`, and an evidence object.

### `POST /api/v1/retailers/{retailer_id}/demand-signal`

Request:

```json
{
  "category_id": 1,
  "product_id": 2,
  "source": "report"
}
```

`source` may be `onboarding`, `report`, `order`, `reorder`, or `browse`.

Response includes `id`, `retailer_id`, `category_id`, `category_name`, `product_id`, `source`, and `created_at`.

## Distributors

All distributor routes require authentication.

### `POST /api/v1/distributors/onboarding`

Requires a distributor user.

Request:

```json
{
  "business_name": "ABC Distribution",
  "village_name": "Rampur",
  "block": "Block A",
  "district": "District A",
  "service_radius_km": 20,
  "moq_default": 10
}
```

Response includes `id`, `user_id`, `business_name`, `location_id`, `service_radius_km`, and `moq_default`.

### `GET /api/v1/distributors/{distributor_id}/dashboard`

Returns `distributor`, `top_opportunities`, `catalogue_count`, and `pending_orders`.

The distributor object includes `id`, `business_name`, `location`, and `service_radius_km`.

### `GET /api/v1/distributors/{distributor_id}/opportunities`

Returns:

```json
{ "opportunities": [] }
```

The result is deduplicated to the highest-scoring opportunity per category within the service radius.

## Catalogue

All catalogue routes require authentication. Create and update require a distributor user.

### `POST /api/v1/catalogue-items`

Request:

```json
{ "product_id": 2, "price": 120, "moq": 10, "stock_qty": 100 }
```

The route upserts an existing product for the distributor.

### `PUT /api/v1/catalogue-items/{item_id}`

Uses the same request and response shape as create.

### `GET /api/v1/catalogue-items/distributor/{distributor_id}`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "distributor_id": 3,
      "product_id": 2,
      "product_name": "Paneer",
      "category_name": "Dairy",
      "price": 120,
      "moq": 10,
      "stock_qty": 100
    }
  ]
}
```

## Orders

All order routes require authentication.

### `POST /api/v1/orders`

Creates an order for the authenticated retailer.

Request:

```json
{
  "distributor_id": 3,
  "items": [
    { "product_id": 2, "qty": 20, "unit_price": 120 }
  ]
}
```

Response includes `id`, `retailer_id`, `distributor_id`, `distributor_name`, `status`, `total_amount`, `created_at`, and item rows.

### `PATCH /api/v1/orders/{order_id}/status`

Requires the owning distributor or an admin.

Request:

```json
{ "status": "accepted" }
```

Allowed transitions are `requested` to `accepted`, `accepted` to `preparing`, and `preparing` to `delivered`.

Response:

```json
{ "id": 10, "status": "accepted" }
```

### `GET /api/v1/orders/retailer/{retailer_id}`

Response:

```json
{ "orders": [] }
```

Each order includes its item rows.

### `GET /api/v1/orders/distributor/{distributor_id}/incoming`

Response:

```json
{ "orders": [] }
```

Incoming order rows include `retailer_id`, `retailer_village`, `distributor_id`, `status`, `total_amount`, `created_at`, and items.

### `GET /api/v1/orders/{order_id}/reorder-suggestion`

Response:

```json
{
  "reorder_suggestions": [
    {
      "category_id": 1,
      "category_name": "Dairy",
      "last_order_date": "2026-01-01",
      "days_since_last_order": 12,
      "historical_avg_gap_days": 20,
      "flag": "Reorder overdue",
      "suggested_qty": 20,
      "last_qty": 15,
      "evidence_label": "..."
    }
  ]
}
```

## Opportunities

All opportunity routes require authentication.

### `GET /api/v1/opportunities/{location_id}/{category_id}`

Returns one opportunity with `opportunity_score`, `confidence`, `category_id`, `category_name`, `location_id`, `village_name`, and `evidence_object`.

### `GET /api/v1/opportunities/location/{location_id}`

Returns:

```json
{ "location": { "id": 1, "village_name": "Rampur" }, "opportunities": [] }
```

An evidence object contains `recommendation_type`, `target`, `score`, `confidence`, `evidence`, `warnings`, and `generated_at`.

## Government schemes

Both routes require authentication.

### `GET /api/v1/schemes`

Optional query parameters: `business_type` and `location_id`.

Returns an array of scheme objects with `id`, `name`, `eligibility_factors`, `required_documents`, `source_url`, `last_verified_date`, `contribution_pct`, `indicative_rate_low`, `indicative_rate_high`, and `tenure_years`.

The current backend returns all schemes; query filtering should be implemented before relying on it for personalized eligibility.

### `POST /api/v1/schemes/calculate`

Request:

```json
{ "loan_amount": 100000, "scheme_id": 1 }
```

Response includes `scheme_name`, `requested_amount`, `government_contribution`, `beneficiary_contribution`, `indicative_monthly_emi_low`, `indicative_monthly_emi_high`, `tenure_years`, `source_url`, and the indicative-only `disclaimer`.

## AI explanation

### `POST /api/v1/ai/explain`

Requires authentication. The frontend sends the evidence object generated by the deterministic scoring engine.

Request:

```json
{
  "evidence_object": {
    "recommendation_type": "opportunity",
    "target": "Paneer",
    "score": 84,
    "confidence": "medium",
    "evidence": [],
    "warnings": [],
    "generated_at": "2026-01-01T00:00:00Z"
  }
}
```

Response:

```json
{
  "explanation_text": "Short generated or deterministic explanation.",
  "is_fallback": true,
  "evidence_chips": []
}
```

## Admin analytics

All admin analytics routes require an authenticated user with the `admin` role.

### `GET /api/v1/analytics/signals/feed`

Response:

```json
{
  "signals": [
    {
      "id": 1,
      "source": "report",
      "category": "Dairy",
      "village": "Rampur",
      "block": "Block A",
      "created_at": "2026-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

### `GET /api/v1/analytics/guardrail-rejections`

Response contains `rejections` with `id`, `payload`, and `created_at`, plus `total`.

### `GET /api/v1/analytics/opportunities/summary`

Response:

```json
{ "opportunities": [] }
```

The current backend returns the top 20 positive opportunity calculations.

## Production checklist

- Set a unique `SECRET_KEY` in Render.
- Use the Render PostgreSQL URL, not a relative SQLite path.
- Restrict backend CORS to the Vercel domain.
- Keep `NEXT_PUBLIC_API_URL` pointed at the backend origin without a trailing slash.
- Seed demo data only in a non-production environment.
- Test login, onboarding, one demand signal, one stock plan, one order, and one distributor status transition after deployment.
- Monitor Render logs for database connection errors and AI timeout latency.
- Add migrations before changing SQLAlchemy models in production.
- Add server-side ownership checks for profile, order, catalogue, and opportunity IDs before exposing sensitive multi-tenant data.

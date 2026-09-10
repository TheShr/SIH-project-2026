const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export type Session = {
  access_token: string
  token_type: string
  user_id: number
  role: 'retailer' | 'distributor' | 'admin'
  email: string
  retailer_id?: number | null
  distributor_id?: number | null
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('sanket_access_token') : null
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    cache: 'no-store',
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // Keep the HTTP error when the backend does not return JSON.
    }
    throw new ApiError(detail, response.status)
  }

  return response.json() as Promise<T>
}

export type HealthResponse = {
  status: string
}

export type Category = {
  id: number
  name: string
}

export type CategoriesResponse = {
  categories: Category[]
}

export type Product = Category & { default_unit: string; category_id?: number; category_name?: string }
export type Opportunity = {
  opportunity_score: number
  confidence: string
  category_id: number
  category_name: string
  location_id: number
  village_name?: string
  evidence_object: EvidenceObject
}
export type EvidenceItem = { type: string; value: string | number; label: string }
export type EvidenceObject = {
  recommendation_type: string
  target: string
  score: number
  confidence: string
  evidence: EvidenceItem[]
  warnings: string[]
  generated_at: string
}
export type StockPlanItem = { category_id: number; category_name: string; product_id?: number; product_name: string; recommended_qty: number; unit_price: number; total_cost: number; distributor_id?: number; distributor_name: string; supplier_distance_km: number; confidence: string; evidence: EvidenceObject }
export type StockPlan = { retailer_id: number; budget_total: number; budget_allocated: number; unallocated_buffer: number; items: StockPlanItem[]; evidence_lines: string[] }
export type OrderItem = { id: number; product_id: number; product_name?: string; qty: number; unit_price: number }
export type Order = { id: number; retailer_id?: number; distributor_id: number; distributor_name?: string; retailer_village?: string; status: string; total_amount: number; created_at: string; items: OrderItem[] }
export type CatalogueItem = { id: number; distributor_id: number; product_id: number; product_name: string; category_name?: string; price: number; moq: number; stock_qty: number }
export type Scheme = { id: number; name: string; eligibility_factors: string; required_documents: string; source_url: string; last_verified_date: string; contribution_pct: number; indicative_rate_low: number; indicative_rate_high: number; tenure_years: number }

export const auth = {
  login: (body: { email: string; password: string }) => apiFetch<Session>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  register: (body: { email: string; password: string; phone?: string; role: Session['role'] }) => apiFetch<Session>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(body) }),
}

export const products = {
  all: () => apiFetch<{ products: Product[] }>('/api/v1/products'),
  categories: () => apiFetch<CategoriesResponse>('/api/v1/products/categories'),
  byCategory: (categoryId: number) => apiFetch<{ products: Product[] }>(`/api/v1/products/categories/${categoryId}/products`),
}

export const retailers = {
  dashboard: (id: number) => apiFetch<{ retailer: { id: number; business_type: string; village_name: string; block: string; district: string; budget: number }; top_opportunities: Opportunity[]; stock_plan_summary: { budget_allocated: number; item_count: number }; recent_orders: Order[] }>(`/api/v1/retailers/${id}/dashboard`),
  stockPlan: (id: number) => apiFetch<StockPlan>(`/api/v1/retailers/${id}/stock-plan`),
  demandSignal: (id: number, body: { category_id: number; product_id?: number; source?: string }) => apiFetch('/api/v1/retailers/' + id + '/demand-signal', { method: 'POST', body: JSON.stringify(body) }),
  onboarding: (body: Record<string, unknown>) => apiFetch('/api/v1/retailers/onboarding', { method: 'POST', body: JSON.stringify(body) }),
}

export const distributors = {
  dashboard: (id: number) => apiFetch<{ distributor: { id: number; business_name: string; location: string; service_radius_km: number }; top_opportunities: Opportunity[]; catalogue_count: number; pending_orders: number }>(`/api/v1/distributors/${id}/dashboard`),
  opportunities: (id: number) => apiFetch<{ opportunities: Opportunity[] }>(`/api/v1/distributors/${id}/opportunities`),
  onboarding: (body: Record<string, unknown>) => apiFetch('/api/v1/distributors/onboarding', { method: 'POST', body: JSON.stringify(body) }),
}

export const catalogue = {
  list: (id: number) => apiFetch<{ items: CatalogueItem[] }>(`/api/v1/catalogue-items/distributor/${id}`),
  save: (body: { product_id: number; price: number; moq: number; stock_qty: number }, id?: number) => apiFetch<CatalogueItem>(id ? `/api/v1/catalogue-items/${id}` : '/api/v1/catalogue-items', { method: id ? 'PUT' : 'POST', body: JSON.stringify(body) }),
}

export const orders = {
  retailer: (id: number) => apiFetch<{ orders: Order[] }>(`/api/v1/orders/retailer/${id}`),
  incoming: (id: number) => apiFetch<{ orders: Order[] }>(`/api/v1/orders/distributor/${id}/incoming`),
  create: (body: { distributor_id: number; items: { product_id: number; qty: number; unit_price: number }[] }) => apiFetch<Order>('/api/v1/orders', { method: 'POST', body: JSON.stringify(body) }),
  updateStatus: (id: number, status: string) => apiFetch<{ id: number; status: string }>(`/api/v1/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  reorder: (id: number) => apiFetch<{ reorder_suggestions: { category_name: string; flag: string; suggested_qty: number; evidence_label: string }[] }>(`/api/v1/orders/${id}/reorder-suggestion`),
}

export const opportunities = {
  location: (id: number) => apiFetch<{ location: { id: number; village_name: string }; opportunities: Opportunity[] }>(`/api/v1/opportunities/location/${id}`),
  detail: (locationId: number, categoryId: number) => apiFetch<Opportunity>(`/api/v1/opportunities/${locationId}/${categoryId}`),
}

export const schemes = {
  list: () => apiFetch<Scheme[]>('/api/v1/schemes'),
  calculate: (body: { loan_amount: number; scheme_id: number }) => apiFetch<Record<string, string | number>>('/api/v1/schemes/calculate', { method: 'POST', body: JSON.stringify(body) }),
}

export const ai = {
  explain: (evidence_object: EvidenceObject) => apiFetch<{ explanation_text: string; is_fallback: boolean; evidence_chips: EvidenceItem[] }>('/api/v1/ai/explain', { method: 'POST', body: JSON.stringify({ evidence_object }) }),
}

export const analytics = {
  signals: () => apiFetch<{ signals: { id: number; source: string; category: string; village: string; block: string; created_at: string }[]; total: number }>('/api/v1/analytics/signals/feed'),
  coverage: () => apiFetch<{ opportunities: Opportunity[] }>('/api/v1/analytics/opportunities/summary'),
  rejections: () => apiFetch<{ rejections: { id: number; payload: string; created_at: string }[]; total: number }>('/api/v1/analytics/guardrail-rejections'),
}
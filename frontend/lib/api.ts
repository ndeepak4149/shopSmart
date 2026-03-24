const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Listing {
  id: string;
  title: string;
  price: number;
  url: string;
  seller_name: string;
  source: string;
  image_url: string | null;
  rating: number | null;
  review_count: number | null;
  in_stock: boolean;
  shipping_info: string | null;
  is_local: boolean;
  lat: number | null;
  lon: number | null;
  rank: number;
  score: number;
  reason: string;
  is_top_pick: boolean;
  condition: "new" | "refurbished" | "open_box" | "used" | "parts";
  value_score: number;
  explanation: string;
}

export interface LocalStore {
  name: string;
  lat: number;
  lon: number;
  rating: number | null;
  review_count: number | null;
  source: string;
  stock_confidence: "high" | "medium" | "low" | "unknown";
  stock_note: string;
  distance_km: number | null;
  maps_url: string | null;
  place_id: string | null;
}

export interface SearchResponse {
  query: string;
  top_picks: Listing[];
  other_results: Listing[];
  local_stores: LocalStore[];
  total_found: number;
}

export interface ReviewHighlight {
  source: string;
  text: string;
  sentiment: "positive" | "neutral" | "negative";
}

export interface PriceHistory {
  day: number;
  price: number;
}

export interface ProductAnalysis {
  verdict: string;
  pros: string[];
  cons: string[];
  who_its_for: string;
  value_rating: "excellent" | "good" | "fair" | "poor";
  review_highlights: ReviewHighlight[];
}

export interface SellerAnalysis {
  verdict: string;
  trust_score: "high" | "medium" | "low";
  strengths: string[];
  watch_out_for: string[];
  shipping_reputation: string;
  return_policy_note: string;
  customer_feedback: ReviewHighlight[];
}

export interface PriceEstimate {
  listed_price: number;
  estimated_shipping: number;
  estimated_hidden_fees: number;
  estimated_final: number;
  confidence: "High" | "Medium" | "Low";
  savings_vs_estimate: number;
  price_history: PriceHistory[];
  data_note: string;
}

export interface AnalyzeResponse {
  price: PriceEstimate;
  product_analysis: ProductAnalysis;
  seller_analysis: SellerAnalysis;
  raw_reviews: {
    product: { source: string; text: string }[];
    seller: { source: string; text: string }[];
  };
  direct_url: string | null;
}

// Calls the backend /analyze endpoint and returns price estimate, AI analysis, and a direct product URL
export async function analyzeProduct(params: {
  title: string;
  seller: string;
  price: number;
  source: string;
  url?: string;
}): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_URL}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Analysis failed");
  return res.json();
}

export interface PlaceDetails {
  name: string;
  address: string;
  phone: string;
  website: string;
  rating: number | null;
  review_count: number | null;
  price_level: number | null;
  open_now: boolean | null;
  weekday_hours: string[];
  photo_url: string | null;
  is_closed_permanently: boolean;
  maps_url: string;
}

// Fetches rich Google Places details (address, hours, phone, photo) for a store pin popup
export async function fetchPlaceDetails(placeId: string): Promise<PlaceDetails> {
  const res = await fetch(`${API_URL}/api/v1/place/${encodeURIComponent(placeId)}`);
  if (!res.ok) throw new Error("Place details fetch failed");
  return res.json();
}

// Sends a search query (with optional GPS coords or city) to the backend and returns ranked listings
export async function searchProducts(
  query: string,
  lat?: number,
  lon?: number,
  city?: string
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (lat) params.append("lat", String(lat));
  if (lon) params.append("lon", String(lon));
  if (city) params.append("city", city);

  const res = await fetch(`${API_URL}/api/v1/search?${params}`);
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

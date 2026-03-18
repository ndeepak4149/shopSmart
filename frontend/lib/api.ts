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
}

export interface LocalStore {
  name: string;
  lat: number;
  lon: number;
  rating: number | null;
  review_count: number | null;
  source: string;
}

export interface SearchResponse {
  query: string;
  top_picks: Listing[];
  other_results: Listing[];
  local_stores: LocalStore[];
  total_found: number;
}

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

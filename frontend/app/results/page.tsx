"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { searchProducts } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import ResultCard from "@/components/ResultCard";

// Mapbox GL JS requires browser APIs — dynamic import with ssr:false prevents server-side errors
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

function ResultsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-white rounded-2xl border border-slate-100 p-4 flex gap-4">
          <div className="w-20 h-20 bg-slate-100 rounded-xl flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-slate-100 rounded w-1/3" />
            <div className="h-4 bg-slate-100 rounded w-3/4" />
            <div className="h-3 bg-slate-100 rounded w-1/2" />
          </div>
          <div className="w-16 h-8 bg-slate-100 rounded" />
        </div>
      ))}
    </div>
  );
}

function ResultsContent() {
  const params = useSearchParams();
  const query = params.get("q") || "";
  const lat = params.get("lat") ? Number(params.get("lat")) : undefined;
  const lon = params.get("lon") ? Number(params.get("lon")) : undefined;
  const city = params.get("city") || undefined;
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["search", query, lat, lon, city],
    queryFn: () => searchProducts(query, lat, lon, city),
    enabled: !!query,
  });

  if (!query) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-slate-400">
        <p className="text-lg font-medium">No search query</p>
        <Link href="/" className="mt-4 text-brand-600 hover:underline text-sm">Go back home</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-full">
      {/* Left: Results */}
      <div className="flex-1 min-w-0 overflow-y-auto space-y-6 pb-8">
        {isLoading && <ResultsSkeleton />}

        {isError && (
          <div className="card p-8 text-center">
            <p className="text-slate-500 font-medium">Something went wrong. Please try again.</p>
            <Link href="/" className="mt-3 inline-block text-brand-600 hover:underline text-sm">Back to home</Link>
          </div>
        )}

        {data && (
          <>
            {/* Summary bar: total result count and local store count */}
            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>
                <span className="font-semibold text-slate-900">{data.total_found}</span> results for{" "}
                <span className="font-semibold text-slate-900">&ldquo;{data.query}&rdquo;</span>
              </span>
              {data.local_stores.length > 0 && (
                <span className="flex items-center gap-1 text-green-600 font-medium">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                  </svg>
                  {data.local_stores.length} stores within 50 miles
                </span>
              )}
            </div>

            {/* AI-selected Top Picks section — up to 8 best matches highlighted */}
            {data.top_picks.length > 0 && (
              <section>
                <h2 className="section-title mb-4">
                  <span className="w-7 h-7 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-lg flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                  </span>
                  Top Picks
                  <span className="text-sm font-normal text-slate-400 ml-1">AI-selected best options</span>
                </h2>
                <div className="space-y-3">
                  {data.top_picks.map((listing) => (
                    <ResultCard key={listing.id} listing={listing} query={query} />
                  ))}
                </div>
              </section>
            )}

            {/* All remaining results with a 'Show more' toggle after the first 6 */}
            {data.other_results.length > 0 && (
              <section>
                <h2 className="section-title mb-4">
                  <span className="w-7 h-7 bg-slate-100 rounded-lg flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2">
                      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>
                      <line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/>
                      <line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                    </svg>
                  </span>
                  All Results
                </h2>
                <div className="space-y-3">
                  {(showAll ? data.other_results : data.other_results.slice(0, 6)).map((listing) => (
                    <ResultCard key={listing.id} listing={listing} query={query} />
                  ))}
                </div>
                {!showAll && data.other_results.length > 6 && (
                  <button
                    onClick={() => setShowAll(true)}
                    className="mt-4 w-full py-3 rounded-xl border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors"
                  >
                    Show {data.other_results.length - 6} more results
                  </button>
                )}
              </section>
            )}

            {/* Scrollable list of nearby stores with distance, rating, and stock confidence */}
            {data.local_stores.length > 0 && (
              <section>
                <h2 className="section-title mb-4">
                  <span className="w-7 h-7 bg-green-100 rounded-lg flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2">
                      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                    </svg>
                  </span>
                  Nearby Stores
                  <span className="text-sm font-normal text-slate-400 ml-1">within 50 miles</span>
                </h2>
                <div className="space-y-2">
                  {data.local_stores.map((store, i) => {
                    const confColor: Record<string, string> = {
                      high: "bg-green-100 text-green-700",
                      medium: "bg-amber-100 text-amber-700",
                      low: "bg-indigo-100 text-indigo-700",
                      unknown: "bg-slate-100 text-slate-500",
                    };
                    const confLabel: Record<string, string> = {
                      high: "Likely in stock",
                      medium: "May be in stock",
                      low: "Call ahead",
                      unknown: "Unknown",
                    };
                    const distMi = store.distance_km != null
                      ? (store.distance_km * 0.621371).toFixed(1) + " mi"
                      : null;
                    return (
                      <div key={i} className="bg-white rounded-xl border border-slate-100 px-4 py-3 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center flex-shrink-0">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2">
                            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-800 text-sm truncate">{store.name}</p>
                          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                            {store.rating && (
                              <span className="text-xs text-slate-500">⭐ {store.rating.toFixed(1)}</span>
                            )}
                            {distMi && (
                              <span className="text-xs text-slate-400">{distMi}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${confColor[store.stock_confidence] || confColor.unknown}`}>
                            {confLabel[store.stock_confidence] || "Unknown"}
                          </span>
                          {store.maps_url && (
                            <a
                              href={store.maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-indigo-600 hover:underline font-medium"
                            >
                              Directions ↗
                            </a>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {data.top_picks.length === 0 && data.other_results.length === 0 && (
              <div className="card p-12 text-center">
                <p className="text-slate-500 text-lg font-medium">No results found</p>
                <p className="text-slate-400 text-sm mt-2">Try a different search term</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Right panel: sticky map — always visible so users can see local stores while scrolling results */}
      <div className="lg:w-[380px] xl:w-[440px] flex-shrink-0">
        <div className="sticky top-6 h-[calc(100vh-120px)] rounded-2xl overflow-hidden bg-slate-100 flex flex-col">
          {/* Overlay shown when no city/GPS is provided — prompts the user to add their location */}
          {!city && !lat && !isLoading && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-50 rounded-2xl gap-3 p-6 text-center">
              <div className="w-14 h-14 bg-brand-50 rounded-2xl flex items-center justify-center">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="1.5">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                </svg>
              </div>
              <div>
                <p className="font-semibold text-slate-800">Find nearby stores</p>
                <p className="text-sm text-slate-500 mt-1">Search with a city name to see local stores on the map</p>
              </div>
              <Link
                href={`/?q=${encodeURIComponent(query)}&prompt_city=1`}
                className="mt-1 px-4 py-2 bg-brand-600 text-white text-sm font-semibold rounded-xl hover:bg-brand-700 transition-colors"
              >
                Add your city
              </Link>
            </div>
          )}
          <MapView
            stores={data?.local_stores || []}
            centerLat={lat}
            centerLon={lon}
          />
        </div>
      </div>
    </div>
  );
}

function ResultsNav() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const city = searchParams.get("city") || "";

  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-slate-100 shadow-sm">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-violet-600 rounded-lg flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <span className="font-bold text-slate-900 text-lg">ShopSmart</span>
        </Link>
        <div className="flex-1">
          <SearchBar defaultValue={query} defaultCity={city} compact />
        </div>
      </div>
    </nav>
  );
}

export default function ResultsPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Suspense fallback={
        <nav className="sticky top-0 z-50 bg-white border-b border-slate-100 shadow-sm h-16" />
      }>
        <ResultsNav />
      </Suspense>
      <div className="max-w-7xl mx-auto px-6 py-6 h-[calc(100vh-64px)]">
        <Suspense fallback={<ResultsSkeleton />}>
          <ResultsContent />
        </Suspense>
      </div>
    </div>
  );
}

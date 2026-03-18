"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface SearchBarProps {
  defaultValue?: string;
  defaultCity?: string;
  compact?: boolean;
}

export default function SearchBar({ defaultValue = "", defaultCity = "", compact = false }: SearchBarProps) {
  const [query, setQuery] = useState(defaultValue);
  const [city, setCity] = useState(defaultCity);
  const [locating, setLocating] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const params = new URLSearchParams({ q: query.trim() });
    if (coords) { params.set("lat", String(coords.lat)); params.set("lon", String(coords.lon)); }
    else if (city.trim()) params.set("city", city.trim());
    router.push(`/results?${params}`);
  };

  const getLocation = () => {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }); setLocating(false); },
      () => setLocating(false)
    );
  };

  if (compact) {
    return (
      <form onSubmit={handleSearch} className="flex gap-2 w-full max-w-2xl">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for a product..."
          className="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
        <button type="submit" className="bg-brand-600 hover:bg-brand-700 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm">
          Search
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSearch} className="w-full max-w-2xl space-y-3">
      {/* Main search input */}
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are you looking for?"
          className="w-full bg-white border border-slate-200 rounded-2xl pl-12 pr-5 py-4 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all text-base shadow-sm"
          autoFocus
        />
      </div>

      {/* Location row */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
            </svg>
          </div>
          <input
            value={coords ? "Using your location" : city}
            onChange={(e) => { setCity(e.target.value); setCoords(null); }}
            placeholder="Your city (e.g. Austin, TX)"
            disabled={!!coords}
            className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-4 py-3 text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all text-sm disabled:bg-slate-50 disabled:text-slate-500"
          />
        </div>
        <button
          type="button"
          onClick={getLocation}
          disabled={locating || !!coords}
          className="flex items-center gap-1.5 px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-600 text-sm font-medium hover:bg-slate-50 hover:border-slate-300 transition-all disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {locating ? (
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          ) : coords ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-500">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>
            </svg>
          )}
          {coords ? "Located" : locating ? "Locating..." : "Use GPS"}
        </button>
      </div>

      <button type="submit" className="w-full btn-primary py-4 text-base">
        Find Best Prices
      </button>
    </form>
  );
}

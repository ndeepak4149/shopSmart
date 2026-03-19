"use client";

import { useState, useEffect } from "react";
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
  const [locationDenied, setLocationDenied] = useState(false);
  const router = useRouter();

  // On mount: restore GPS coords from localStorage so repeat searches keep the location set
  useEffect(() => {
    try {
      const saved = localStorage.getItem("shopsmart_coords");
      if (saved) {
        setCoords(JSON.parse(saved));
        return;
      }
    } catch {}
    // No saved coords — silently auto-detect on first visit if the browser allows it
    if ("geolocation" in navigator) {
      autoDetect();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveAndSetCoords = (c: { lat: number; lon: number }) => {
    setCoords(c);
    try { localStorage.setItem("shopsmart_coords", JSON.stringify(c)); } catch {}
  };

  const autoDetect = () => {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        saveAndSetCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocating(false);
      },
      () => {
        setLocating(false);
        setLocationDenied(true);
      },
      { timeout: 8000 }
    );
  };

  const getLocation = () => {
    setLocating(true);
    setLocationDenied(false);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        saveAndSetCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setLocating(false);
      },
      () => { setLocating(false); setLocationDenied(true); }
    );
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const params = new URLSearchParams({ q: query.trim() });
    if (coords) { params.set("lat", String(coords.lat)); params.set("lon", String(coords.lon)); }
    else if (city.trim()) params.set("city", city.trim());
    router.push(`/results?${params}`);
  };

  if (compact) {
    return (
      <form onSubmit={handleSearch} className="flex gap-2 w-full max-w-2xl items-center">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for a product..."
          className="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
        {coords && (
          <span className="flex items-center gap-1 text-xs text-green-600 font-medium whitespace-nowrap">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
            </svg>
            GPS
          </span>
        )}
        <button type="submit" className="bg-brand-600 hover:bg-brand-700 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm">
          Search
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSearch} className="w-full max-w-2xl space-y-3">
      {/* Main search query input with magnifying-glass icon */}
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

      {/* Location row: city text input OR GPS detected coordinates */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
            </svg>
          </div>
          <input
            value={coords ? "📍 Using your GPS location" : city}
            onChange={(e) => { setCity(e.target.value); setCoords(null); }}
            placeholder="Your city (e.g. Austin, TX)"
            disabled={!!coords}
            className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-8 py-3 text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all text-sm disabled:bg-green-50 disabled:text-green-700 disabled:border-green-200"
          />
          {coords && (
            <button
              type="button"
              onClick={() => { setCoords(null); try { localStorage.removeItem("shopsmart_coords"); } catch {} }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              title="Clear location"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={getLocation}
          disabled={locating || !!coords}
          className={`flex items-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium transition-all disabled:cursor-not-allowed whitespace-nowrap ${
            coords
              ? "border-green-200 bg-green-50 text-green-700 disabled:opacity-100"
              : locationDenied
              ? "border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-60"
          }`}
        >
          {locating ? (
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          ) : coords ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          ) : locationDenied ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>
            </svg>
          )}
          {coords ? "Located" : locating ? "Detecting..." : locationDenied ? "Retry GPS" : "Use GPS"}
        </button>
      </div>

      <button type="submit" className="w-full btn-primary py-4 text-base">
        Find Best Prices
      </button>
    </form>
  );
}

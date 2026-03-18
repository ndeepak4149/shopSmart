"use client";

import { useEffect, useRef } from "react";
import { LocalStore } from "@/lib/api";

interface MapViewProps {
  stores: LocalStore[];
  centerLat?: number;
  centerLon?: number;
}

export default function MapView({ stores, centerLat, centerLon }: MapViewProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<unknown>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) {
      console.warn("Mapbox token not set");
      return;
    }

    // Dynamically import mapbox to avoid SSR issues
    import("mapbox-gl").then((mapboxgl) => {
      const mapboxGl = mapboxgl.default;
      mapboxGl.accessToken = token;

      const defaultLat = centerLat || stores[0]?.lat || 30.2672;
      const defaultLon = centerLon || stores[0]?.lon || -97.7431;

      const map = new mapboxGl.Map({
        container: mapContainer.current!,
        style: "mapbox://styles/mapbox/light-v11",
        center: [defaultLon, defaultLat],
        zoom: 11,
      });

      mapRef.current = map;

      map.on("load", () => {
        stores.forEach((store) => {
          if (!store.lat || !store.lon) return;

          // Create custom marker element
          const el = document.createElement("div");
          el.className = "store-marker";
          el.style.cssText = `
            width: 36px; height: 36px;
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: 3px solid white;
            box-shadow: 0 4px 12px rgba(99,102,241,0.4);
            cursor: pointer;
          `;

          // Popup with store info
          const popup = new mapboxGl.Popup({ offset: 25, closeButton: false }).setHTML(`
            <div style="font-family: Inter, sans-serif; padding: 4px;">
              <p style="font-weight: 700; font-size: 14px; margin: 0 0 4px; color: #0f172a;">${store.name}</p>
              ${store.rating ? `<p style="font-size: 12px; color: #64748b; margin: 0;">⭐ ${store.rating.toFixed(1)} · ${store.review_count?.toLocaleString() || "?"} reviews</p>` : ""}
            </div>
          `);

          new mapboxGl.Marker({ element: el })
            .setLngLat([store.lon, store.lat])
            .setPopup(popup)
            .addTo(map);
        });
      });
    });

    return () => {
      if (mapRef.current) {
        (mapRef.current as { remove: () => void }).remove();
        mapRef.current = null;
      }
    };
  }, [stores, centerLat, centerLon]);

  if (!stores.length) {
    return (
      <div className="w-full h-full rounded-2xl bg-slate-100 flex flex-col items-center justify-center text-slate-400 gap-3">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
        </svg>
        <div className="text-center">
          <p className="font-medium text-sm">No local stores found</p>
          <p className="text-xs mt-1">Share your location for nearby results</p>
        </div>
      </div>
    );
  }

  return <div ref={mapContainer} className="w-full h-full rounded-2xl overflow-hidden" />;
}

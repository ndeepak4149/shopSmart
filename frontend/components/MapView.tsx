"use client";

import { useEffect, useRef } from "react";
import { LocalStore, fetchPlaceDetails } from "@/lib/api";

interface MapViewProps {
  stores: LocalStore[];
  centerLat?: number;
  centerLon?: number;
}

function fmtDist(km: number | null): string {
  if (km == null) return "";
  const miles = km * 0.621371;
  return miles < 0.1 ? `${(miles * 5280).toFixed(0)} ft` : `${miles.toFixed(1)} mi`;
}

function priceLevelStr(level: number | null): string {
  if (level == null) return "";
  return ["", "$", "$$", "$$$", "$$$$"][level] || "";
}

/** Skeleton popup rendered instantly when a pin is clicked while Place Details loads in the background */
function skeletonHtml(store: LocalStore): string {
  const distText = store.distance_km != null
    ? `<span style="color:#94a3b8;font-size:11px;">${fmtDist(store.distance_km)} away</span>`
    : "";
  const stars = store.rating
    ? `⭐ ${store.rating.toFixed(1)} · ${store.review_count?.toLocaleString() || "?"} reviews`
    : "";

  return `
    <div id="popup-inner" style="font-family:Inter,sans-serif;min-width:220px;max-width:280px;">
      <p style="font-weight:700;font-size:14px;margin:0 0 2px;color:#0f172a;line-height:1.3;">${store.name}</p>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        ${stars ? `<span style="font-size:12px;color:#64748b;">${stars}</span>` : ""}
        ${distText}
      </div>
      <div style="height:2px;background:#f1f5f9;border-radius:2px;overflow:hidden;margin-bottom:8px;">
        <div style="height:100%;width:60%;background:linear-gradient(90deg,#e2e8f0 25%,#f8fafc 50%,#e2e8f0 75%);background-size:200% 100%;animation:shimmer 1.4s infinite;">
        </div>
      </div>
      <p style="font-size:11px;color:#94a3b8;margin:0 0 8px;">Loading details…</p>
      <p style="font-size:11px;color:#f59e0b;font-weight:600;margin:0;background:#fffbeb;padding:5px 8px;border-radius:6px;">
        📞 Call ahead to confirm product availability
      </p>
      <style>@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}</style>
    </div>
  `;
}

/** Rich popup HTML built from the Places Details API response — replaces the skeleton once data arrives */
function richHtml(store: LocalStore, d: Awaited<ReturnType<typeof fetchPlaceDetails>>): string {
  const dist = store.distance_km != null ? fmtDist(store.distance_km) : "";
  const price = priceLevelStr(d.price_level);

  const openBadge = d.is_closed_permanently
    ? `<span style="background:#fee2e2;color:#dc2626;font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;">Permanently closed</span>`
    : d.open_now === true
      ? `<span style="background:#dcfce7;color:#16a34a;font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;">Open now</span>`
      : d.open_now === false
        ? `<span style="background:#fee2e2;color:#dc2626;font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;">Closed now</span>`
        : "";

  const photo = d.photo_url
    ? `<img src="${d.photo_url}" alt="${d.name}" style="width:100%;height:110px;object-fit:cover;border-radius:8px;margin-bottom:10px;display:block;" />`
    : "";

  const address = d.address
    ? `<p style="font-size:12px;color:#475569;margin:0 0 5px;display:flex;gap:5px;align-items:flex-start;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" style="flex-shrink:0;margin-top:1px"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
        ${d.address}
      </p>`
    : "";

  const phone = d.phone
    ? `<p style="font-size:12px;color:#475569;margin:0 0 5px;display:flex;gap:5px;align-items:center;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 11a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3 .21h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.09 7.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21 15l.01 1.92Z"/></svg>
        <a href="tel:${d.phone}" style="color:#6366f1;text-decoration:none;">${d.phone}</a>
      </p>`
    : "";

  // Today's hours
  const today = new Date().getDay(); // 0=Sun
  const dayIndex = today === 0 ? 6 : today - 1; // Google weekday_text starts Monday
  const todayHours = d.weekday_hours[dayIndex] || "";
  const hoursText = todayHours
    ? `<p style="font-size:12px;color:#475569;margin:0 0 8px;display:flex;gap:5px;align-items:center;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        ${todayHours.split(": ")[1] || todayHours}
      </p>`
    : "";

  const website = d.website
    ? `<a href="${d.website}" target="_blank" rel="noopener" style="font-size:12px;color:#6366f1;font-weight:600;text-decoration:none;display:flex;align-items:center;gap:4px;">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        Visit website
      </a>`
    : "";

  const mapsLink = `<a href="${d.maps_url}" target="_blank" rel="noopener" style="font-size:12px;color:#6366f1;font-weight:600;text-decoration:none;display:flex;align-items:center;gap:4px;">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
      Directions
    </a>`;

  return `
    <div style="font-family:Inter,sans-serif;min-width:220px;max-width:280px;">
      ${photo}
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;margin-bottom:4px;">
        <p style="font-weight:700;font-size:14px;margin:0;color:#0f172a;line-height:1.3;flex:1;">${d.name}</p>
        ${price ? `<span style="font-size:12px;color:#64748b;flex-shrink:0;">${price}</span>` : ""}
      </div>

      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
        ${d.rating ? `<span style="font-size:12px;color:#64748b;">⭐ ${d.rating.toFixed(1)} · ${d.review_count?.toLocaleString() || "?"}</span>` : ""}
        ${dist ? `<span style="font-size:11px;color:#94a3b8;">${dist} away</span>` : ""}
        ${openBadge}
      </div>

      <div style="height:1px;background:#f1f5f9;margin-bottom:8px;"></div>

      ${address}
      ${phone}
      ${hoursText}

      <div style="display:flex;gap:12px;margin-top:4px;">
        ${mapsLink}
        ${website}
      </div>
      <p style="font-size:11px;color:#b45309;font-weight:600;margin:10px 0 0;background:#fffbeb;padding:5px 8px;border-radius:6px;">
        📞 Call ahead to confirm product availability
      </p>
    </div>
  `;
}

// Inject the pulse-ring keyframe animation once — subsequent calls are no-ops thanks to the ID check
function injectPulseCSS() {
  if (document.getElementById("shopsmart-pin-css")) return;
  const style = document.createElement("style");
  style.id = "shopsmart-pin-css";
  style.textContent = `
    @keyframes ss-ping {
      0%   { transform: scale(1);   opacity: 0.55; }
      80%  { transform: scale(2.8); opacity: 0;    }
      100% { transform: scale(2.8); opacity: 0;    }
    }
    .ss-pin-pulse {
      animation: ss-ping 2s ease-out infinite;
    }
    .ss-pin-pulse-slow {
      animation: ss-ping 2.6s ease-out infinite 0.4s;
    }
  `;
  document.head.appendChild(style);
}

/** Builds a small pulsing dot marker element for a store pin — color encodes stock confidence */
function makePinEl(color: string): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.style.cssText = "position:relative;width:18px;height:18px;cursor:pointer;";

  // Outer pulse ring
  const ring = document.createElement("div");
  ring.className = "ss-pin-pulse";
  ring.style.cssText = `
    position:absolute;inset:0;border-radius:50%;
    background:${color};pointer-events:none;
  `;

  // Inner solid dot
  const dot = document.createElement("div");
  dot.style.cssText = `
    position:absolute;inset:3px;border-radius:50%;
    background:${color};
    border:2px solid white;
    box-shadow:0 2px 8px rgba(0,0,0,0.25);
  `;

  wrap.appendChild(ring);
  wrap.appendChild(dot);
  return wrap;
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

    injectPulseCSS();

    import("mapbox-gl").then((mapboxgl) => {
      const mapboxGl = mapboxgl.default;
      mapboxGl.accessToken = token;

      const defaultLat = centerLat || stores[0]?.lat || 30.2672;
      const defaultLon = centerLon || stores[0]?.lon || -97.7431;

      const map = new mapboxGl.Map({
        container: mapContainer.current!,
        style: "mapbox://styles/mapbox/light-v11",
        center: [defaultLon, defaultLat],
        zoom: 10,
      });

      mapRef.current = map;

      map.on("load", () => {
        // Pin color encodes stock confidence: green = high, amber = medium, indigo = low, slate = unknown
        const pinColor: Record<string, string> = {
          high:    "#16a34a",   // green
          medium:  "#f59e0b",   // amber
          low:     "#6366f1",   // indigo
          unknown: "#94a3b8",   // slate
        };

        // 50-mile radius ring
        if (centerLat && centerLon) {
          const RADIUS_KM = 80.46;
          const pts = 64;
          const coords: [number, number][] = Array.from({ length: pts + 1 }, (_, i) => {
            const a = (i / pts) * 2 * Math.PI;
            const dLat = (RADIUS_KM / 111.32) * Math.cos(a);
            const dLon = (RADIUS_KM / (111.32 * Math.cos((centerLat * Math.PI) / 180))) * Math.sin(a);
            return [centerLon + dLon, centerLat + dLat] as [number, number];
          });

          map.addSource("radius-ring", {
            type: "geojson",
            data: { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [coords] } },
          });
          map.addLayer({ id: "radius-fill", type: "fill", source: "radius-ring", paint: { "fill-color": "#6366f1", "fill-opacity": 0.04 } });
          map.addLayer({ id: "radius-border", type: "line", source: "radius-ring", paint: { "line-color": "#6366f1", "line-width": 1.5, "line-dasharray": [4, 3] } });

          // User location marker — uses a distinct indigo color to stand out from store pins
          const userWrap = document.createElement("div");
          userWrap.style.cssText = "position:relative;width:18px;height:18px;";
          const userRing = document.createElement("div");
          userRing.className = "ss-pin-pulse";
          userRing.style.cssText = "position:absolute;inset:0;border-radius:50%;background:#4f46e5;";
          const userDot = document.createElement("div");
          userDot.style.cssText = "position:absolute;inset:3px;border-radius:50%;background:#4f46e5;border:2px solid white;box-shadow:0 2px 8px rgba(79,70,229,0.4);";
          userWrap.appendChild(userRing);
          userWrap.appendChild(userDot);

          new mapboxGl.Marker({ element: userWrap })
            .setLngLat([centerLon, centerLat])
            .setPopup(new mapboxGl.Popup({ offset: 14, closeButton: false }).setHTML(
              `<p style="font-size:12px;font-weight:600;margin:0;color:#4f46e5;">Your location</p>`
            ))
            .addTo(map);
        }

        // Place a pin for each store; rich place details are fetched lazily on first click
        stores.forEach((store) => {
          if (!store.lat || !store.lon) return;

          const color = pinColor[store.stock_confidence] || pinColor.unknown;
          const el = makePinEl(color);

          const popup = new mapboxGl.Popup({ offset: 14, closeButton: false, maxWidth: "300px" })
            .setHTML(skeletonHtml(store));

          const marker = new mapboxGl.Marker({ element: el })
            .setLngLat([store.lon, store.lat])
            .setPopup(popup)
            .addTo(map);

          // On click: fetch Place Details once and swap the skeleton popup for the rich HTML
          marker.getElement().addEventListener("click", () => {
            if (!store.place_id) return;
            fetchPlaceDetails(store.place_id)
              .then((details) => popup.setHTML(richHtml(store, details)))
              .catch(() => { /* keep skeleton */ });
          });
        });

        // Fit the map viewport to include all store pins (plus the user's location if available)
        if (stores.length > 0) {
          const lons = stores.map(s => s.lon).filter(Boolean) as number[];
          const lats = stores.map(s => s.lat).filter(Boolean) as number[];
          if (centerLon) lons.push(centerLon);
          if (centerLat) lats.push(centerLat);
          map.fitBounds(
            [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
            { padding: 48, maxZoom: 13, duration: 800 }
          );
        }
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
          <p className="text-xs mt-1">Share your location to find stores within 50 miles</p>
        </div>
      </div>
    );
  }

  return <div ref={mapContainer} className="w-full h-full rounded-2xl overflow-hidden" />;
}

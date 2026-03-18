"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { Listing } from "@/lib/api";

interface ResultCardProps {
  listing: Listing;
  query: string;
}

const SOURCE_LABELS: Record<string, string> = {
  channel3: "Web",
  ebay: "eBay",
  google_places: "Local Store",
};

const SOURCE_COLORS: Record<string, string> = {
  channel3: "bg-blue-50 text-blue-700",
  ebay: "bg-amber-50 text-amber-700",
  google_places: "bg-green-50 text-green-700",
};

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg key={star} width="12" height="12" viewBox="0 0 24 24"
          fill={star <= Math.round(rating) ? "#f59e0b" : "none"}
          stroke="#f59e0b" strokeWidth="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      ))}
    </div>
  );
}

export default function ResultCard({ listing, query }: ResultCardProps) {
  const router = useRouter();
  const encodedId = encodeURIComponent(listing.id);
  const encodedQuery = encodeURIComponent(query);

  const handleClick = () => {
    router.push(`/product/${encodedId}?q=${encodedQuery}&title=${encodeURIComponent(listing.title)}&price=${listing.price}&seller=${encodeURIComponent(listing.seller_name)}&url=${encodeURIComponent(listing.url)}&source=${listing.source}`);
  };

  return (
    <div
      onClick={handleClick}
      className={`card p-4 cursor-pointer group ${listing.is_top_pick ? "top-pick-glow border-brand-200" : ""}`}
    >
      <div className="flex gap-4">
        {/* Image */}
        <div className="w-20 h-20 rounded-xl bg-slate-100 flex-shrink-0 overflow-hidden">
          {listing.image_url ? (
            <Image src={listing.image_url} alt={listing.title} width={80} height={80} className="w-full h-full object-contain p-1" unoptimized />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-300">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="flex flex-wrap items-center gap-1.5">
              {listing.is_top_pick && (
                <span className="badge-top-pick">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                  Top Pick
                </span>
              )}
              <span className={`badge ${SOURCE_COLORS[listing.source] || "bg-slate-100 text-slate-600"}`}>
                {SOURCE_LABELS[listing.source] || listing.source}
              </span>
              {listing.is_local && (
                <span className="badge bg-green-50 text-green-700">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
                  Nearby
                </span>
              )}
            </div>
            {/* Price */}
            <div className="text-right flex-shrink-0">
              {listing.price > 0 ? (
                <span className="text-xl font-bold text-slate-900">${listing.price.toFixed(2)}</span>
              ) : (
                <span className="text-sm text-slate-500 font-medium">Price in store</span>
              )}
            </div>
          </div>

          <p className="text-sm font-medium text-slate-800 line-clamp-2 mb-2 group-hover:text-brand-600 transition-colors">
            {listing.title}
          </p>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">{listing.seller_name}</span>
              {listing.rating && (
                <div className="flex items-center gap-1">
                  <StarRating rating={listing.rating} />
                  <span className="text-xs text-slate-500">
                    {listing.rating.toFixed(1)}
                    {listing.review_count ? ` (${listing.review_count.toLocaleString()})` : ""}
                  </span>
                </div>
              )}
            </div>

            {!listing.in_stock && (
              <span className="text-xs text-red-500 font-medium">Out of stock</span>
            )}
          </div>

          {/* Why this pick */}
          {listing.is_top_pick && listing.reason && (
            <div className="mt-2 flex items-center gap-1 text-xs text-brand-600 font-medium">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/>
              </svg>
              {listing.reason}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

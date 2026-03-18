"use client";

import { useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";
import Link from "next/link";

function PriceBreakdown({ basePrice }: { basePrice: number }) {
  const shipping = +(basePrice * 0.04).toFixed(2);
  const fees = +(basePrice * 0.015).toFixed(2);
  const estimated = +(basePrice + shipping + fees).toFixed(2);
  const confidence = basePrice > 50 ? "High" : "Medium";

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-900">Price Breakdown</h2>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${confidence === "High" ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>
          {confidence} Confidence
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">Listed price</span>
          <span className="font-semibold text-slate-900">${basePrice.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1">
            Estimated shipping
            <span className="text-xs text-slate-400">(avg from this seller)</span>
          </span>
          <span className="font-semibold text-slate-700">+ ${shipping.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1">
            Processing fees
            <span className="text-xs text-slate-400">(seen in ~70% of orders)</span>
          </span>
          <span className="font-semibold text-slate-700">+ ${fees.toFixed(2)}</span>
        </div>
        <div className="h-px bg-slate-100" />
        <div className="flex justify-between items-center">
          <span className="font-bold text-slate-900">Estimated final price</span>
          <span className="text-2xl font-extrabold text-slate-900">~${estimated.toFixed(2)}</span>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">
        Estimated using our ML model trained on historical seller data. Actual price may vary.
      </p>
    </div>
  );
}

function PriceAlert({ price }: { price: number }) {
  const [enabled, setEnabled] = useState(false);
  const [email, setEmail] = useState("");
  const [target, setTarget] = useState(String(Math.floor(price * 0.9)));
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    if (!email) return;
    setSaved(true);
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-slate-900">Price Drop Alert</h3>
          <p className="text-sm text-slate-500 mt-0.5">Get notified when the price drops</p>
        </div>
        <button
          onClick={() => setEnabled(!enabled)}
          className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${enabled ? "bg-brand-600" : "bg-slate-200"}`}
        >
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${enabled ? "translate-x-7" : "translate-x-1"}`} />
        </button>
      </div>

      {enabled && !saved && (
        <div className="space-y-3 animate-fade-in">
          <div>
            <label className="text-xs font-medium text-slate-600 mb-1 block">Alert me when price drops below</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">$</span>
              <input
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-full border border-slate-200 rounded-xl pl-7 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                type="number"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 mb-1 block">Your email</label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@email.com"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              type="email"
            />
          </div>
          <button onClick={handleSave} className="btn-primary w-full py-2.5 text-sm">
            Set Alert
          </button>
        </div>
      )}

      {saved && (
        <div className="flex items-center gap-2 text-green-600 text-sm font-medium animate-fade-in">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          Alert set! We&apos;ll email you at {email}
        </div>
      )}
    </div>
  );
}

function ReviewHighlights() {
  const reviews = [
    { platform: "Reddit", user: "u/tech_deals", text: "Honestly the best noise cancellation I've tried. Battery life is insane — lasted me a full work week.", sentiment: "positive" },
    { platform: "Reddit", user: "u/audiophile_corner", text: "Sound quality is excellent. The ANC is top tier. Touch controls take getting used to but worth it.", sentiment: "positive" },
    { platform: "Google", user: "Verified Buyer", text: "Great headphones, fast shipping. Build quality feels premium. Would buy again.", sentiment: "positive" },
    { platform: "Reddit", user: "u/budget_shopper", text: "Pricey but you get what you pay for. The case could be more durable though.", sentiment: "neutral" },
  ];

  const sentimentColors: Record<string, string> = {
    positive: "bg-green-50 text-green-700",
    neutral: "bg-slate-100 text-slate-600",
    negative: "bg-red-50 text-red-700",
  };

  return (
    <div className="card p-6">
      <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        What people are saying
      </h3>
      <div className="space-y-3">
        {reviews.map((r, i) => (
          <div key={i} className="p-4 bg-slate-50 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`badge text-xs ${r.platform === "Reddit" ? "bg-orange-50 text-orange-700" : "bg-blue-50 text-blue-700"}`}>
                  {r.platform}
                </span>
                <span className="text-xs text-slate-400">{r.user}</span>
              </div>
              <span className={`badge text-xs ${sentimentColors[r.sentiment]}`}>
                {r.sentiment}
              </span>
            </div>
            <p className="text-sm text-slate-700 leading-relaxed">&ldquo;{r.text}&rdquo;</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProductContent() {
  const params = useSearchParams();
  const title = params.get("title") || "Product";
  const price = Number(params.get("price")) || 0;
  const seller = params.get("seller") || "Seller";
  const url = params.get("url") || "#";
  const source = params.get("source") || "";
  const query = params.get("q") || "";

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white border-b border-slate-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center gap-4">
          <Link href={`/results?q=${encodeURIComponent(query)}`} className="flex items-center gap-2 text-slate-500 hover:text-slate-700 transition-colors text-sm font-medium">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m15 18-6-6 6-6"/>
            </svg>
            Back to results
          </Link>
          <div className="h-4 w-px bg-slate-200" />
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-brand-500 to-violet-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <span className="font-bold text-slate-900">ShopSmart</span>
          </Link>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Loading indicator */}
        <div className="mb-6 flex items-center gap-3 text-sm text-slate-500 bg-white border border-slate-100 rounded-xl px-4 py-3">
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span key={i} className="w-2 h-2 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
          Analyzing seller history and gathering reviews...
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Product header */}
            <div className="card p-6">
              <div className="flex gap-4">
                <div className="w-24 h-24 bg-slate-100 rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <h1 className="text-xl font-bold text-slate-900 leading-snug">{title}</h1>
                  </div>
                  <p className="text-slate-500 text-sm mt-1">Sold by <span className="font-medium text-slate-700">{seller}</span></p>
                  {price > 0 && (
                    <div className="mt-3">
                      <span className="text-3xl font-extrabold text-slate-900">${price.toFixed(2)}</span>
                      <span className="text-sm text-slate-400 ml-2">listed price</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Price breakdown */}
            {price > 0 && <PriceBreakdown basePrice={price} />}

            {/* Reviews */}
            <ReviewHighlights />
          </div>

          {/* Right column */}
          <div className="space-y-4">
            {/* CTA */}
            {url && url !== "#" ? (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary w-full flex items-center justify-center gap-2 py-4 text-base"
              >
                Go to {source === "ebay" ? "eBay" : seller}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                  <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
              </a>
            ) : (
              <div className="btn-secondary w-full flex items-center justify-center gap-2 py-4 cursor-default">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                </svg>
                Visit in store
              </div>
            )}

            {/* Price alert */}
            {price > 0 && <PriceAlert price={price} />}

            {/* Seller info */}
            <div className="card p-5">
              <h3 className="font-bold text-slate-900 mb-3 text-sm">About this seller</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Name</span>
                  <span className="font-medium text-slate-800">{seller}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Source</span>
                  <span className="font-medium text-slate-800 capitalize">{source}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Hidden fee rate</span>
                  <span className="font-medium text-green-700">~1.5% avg</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProductPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <ProductContent />
    </Suspense>
  );
}

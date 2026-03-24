"use client";

import { useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { analyzeProduct, AnalyzeResponse, Listing, LocalStore } from "@/lib/api";

// ── Icon components — inline SVGs kept small and co-located with usage ──────────────────────
const IconCheck = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-green-500 flex-shrink-0 mt-0.5">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);
const IconX = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-red-400 flex-shrink-0 mt-0.5">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const IconWarn = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-amber-500 flex-shrink-0 mt-0.5">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>
  </svg>
);
const IconStar = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="text-amber-400">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
  </svg>
);

// ── Sentiment badge — colored pill shown next to each review highlight ─────────────────────
function SentimentBadge({ sentiment }: { sentiment: string }) {
  const styles: Record<string, string> = {
    positive: "bg-green-50 text-green-700 border border-green-100",
    neutral:  "bg-slate-100 text-slate-600",
    negative: "bg-red-50 text-red-600 border border-red-100",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[sentiment] || styles.neutral}`}>
      {sentiment}
    </span>
  );
}

// ── Source badge — colored pill identifying where a review came from ──────────────────────
function SourceBadge({ source }: { source: string }) {
  const styles: Record<string, string> = {
    Reddit:      "bg-orange-50 text-orange-700",
    Google:      "bg-blue-50 text-blue-700",
    Trustpilot:  "bg-green-50 text-green-700",
    Amazon:      "bg-amber-50 text-amber-700",
    Yelp:        "bg-red-50 text-red-700",
    Web:         "bg-slate-100 text-slate-600",
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${styles[source] || styles.Web}`}>
      {source}
    </span>
  );
}

// ── Trust score badge — translates 'high/medium/low' into human-friendly labels ─────────
function TrustBadge({ score }: { score: string }) {
  const styles: Record<string, string> = {
    high:   "bg-green-50 text-green-700 border border-green-200",
    medium: "bg-amber-50 text-amber-700 border border-amber-200",
    low:    "bg-red-50 text-red-700 border border-red-200",
  };
  const labels: Record<string, string> = {
    high: "Trusted Seller", medium: "Moderate Trust", low: "Use Caution",
  };
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full ${styles[score] || styles.medium}`}>
      {labels[score] || score}
    </span>
  );
}

// ── Value rating badge — 'excellent/good/fair/poor' shown on the product analysis card ──
function ValueBadge({ rating }: { rating: string }) {
  const styles: Record<string, string> = {
    excellent: "bg-green-50 text-green-700 border border-green-200",
    good:      "bg-blue-50 text-blue-700 border border-blue-200",
    fair:      "bg-amber-50 text-amber-700 border border-amber-200",
    poor:      "bg-red-50 text-red-700 border border-red-200",
  };
  return (
    <span className={`text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide ${styles[rating] || styles.fair}`}>
      {rating} value
    </span>
  );
}

// ── Price breakdown card — shows listed price + estimated fees + final total ─────────────
function PriceBreakdown({ data }: { data: AnalyzeResponse["price"] }) {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-900">Price Breakdown</h2>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
          data.confidence === "High" ? "bg-green-50 text-green-700" :
          data.confidence === "Medium" ? "bg-amber-50 text-amber-700" :
          "bg-red-50 text-red-700"
        }`}>
          {data.confidence} Confidence
        </span>
      </div>

      <div className="space-y-3">
        <Row label="Listed price" value={`$${data.listed_price.toFixed(2)}`} />
        <Row label="Estimated shipping" sub="based on seller history" value={`+ $${data.estimated_shipping.toFixed(2)}`} />
        <Row label="Processing / hidden fees" sub="seen in ~70% of orders" value={`+ $${data.estimated_hidden_fees.toFixed(2)}`} />
        <div className="h-px bg-slate-100" />
        <div className="flex justify-between items-center">
          <span className="font-bold text-slate-900">Estimated final price</span>
          <span className="text-2xl font-extrabold text-slate-900">
            ~${data.estimated_final.toFixed(2)}
          </span>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">{data.data_note}</p>
    </div>
  );
}

function Row({ label, sub, value }: { label: string; sub?: string; value: string }) {
  return (
    <div className="flex justify-between text-sm items-start">
      <span className="text-slate-600">
        {label}
        {sub && <span className="text-xs text-slate-400 ml-1">({sub})</span>}
      </span>
      <span className="font-semibold text-slate-800 ml-4">{value}</span>
    </div>
  );
}

// ── Price history chart — 90-day area chart generated from simulated price history data ──
function PriceHistoryChart({ history, currentPrice }: { history: { day: number; price: number }[]; currentPrice: number }) {
  const minPrice = Math.min(...history.map(h => h.price));
  const maxPrice = Math.max(...history.map(h => h.price));
  const avgPrice = history.reduce((s, h) => s + h.price, 0) / history.length;

  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-slate-900">Price History (90 days)</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400 inline-block"/>Low: ${minPrice.toFixed(0)}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block"/>High: ${maxPrice.toFixed(0)}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300 inline-block"/>Avg: ${avgPrice.toFixed(0)}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={[...history].reverse()} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15}/>
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="day" hide />
          <YAxis domain={["auto", "auto"]} hide />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload[0]) {
                const d = payload[0].payload;
                return (
                  <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs shadow-lg">
                    <p className="font-bold text-slate-900">${Number(payload[0].value).toFixed(2)}</p>
                    <p className="text-slate-400">{d.day === 0 ? "Today" : `${d.day} days ago`}</p>
                  </div>
                );
              }
              return null;
            }}
          />
          <Area type="monotone" dataKey="price" stroke="#6366f1" strokeWidth={2} fill="url(#priceGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
      {currentPrice <= minPrice * 1.02 && (
        <div className="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 rounded-xl px-3 py-2">
          <IconCheck />
          <span className="font-medium">This is near the lowest price in 90 days!</span>
        </div>
      )}
    </div>
  );
}

// ── Price alert widget — sends a real email via Resend when the user sets a target price ──
function PriceAlert({ price, productTitle, seller }: { price: number; productTitle: string; seller: string }) {
  const [enabled, setEnabled] = useState(false);
  const [email, setEmail] = useState("");
  const [target, setTarget] = useState(String(Math.floor(price * 0.9)));
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(false);

  const handleSetAlert = async () => {
    if (!email || !target) return;
    setSubmitting(true);
    setSubmitError(false);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/alerts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            target_price: Number(target),
            product_title: productTitle,
            current_price: price,
            seller,
          }),
        }
      );
      if (!res.ok) throw new Error("failed");
      setSaved(true);
    } catch {
      setSubmitError(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-slate-900">Price Drop Alert</h3>
          <p className="text-sm text-slate-500 mt-0.5">Get notified when price drops</p>
        </div>
        <button
          onClick={() => { setEnabled(!enabled); setSaved(false); setSubmitError(false); }}
          className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${enabled ? "bg-brand-600" : "bg-slate-200"}`}
        >
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${enabled ? "translate-x-7" : "translate-x-1"}`} />
        </button>
      </div>

      {enabled && !saved && (
        <div className="space-y-3">
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
          {submitError && (
            <p className="text-xs text-red-500">Something went wrong — check your email and try again.</p>
          )}
          <button
            onClick={handleSetAlert}
            disabled={submitting || !email}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors"
          >
            {submitting ? "Setting alert…" : "Set Alert"}
          </button>
        </div>
      )}
      {saved && (
        <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
          <IconCheck />
          Alert set! Check your inbox at {email}
        </div>
      )}
    </div>
  );
}

// ── Product analysis card — displays Claude AI verdict, pros/cons, and review highlights
function ProductAnalysisCard({ data }: { data: AnalyzeResponse["product_analysis"] }) {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-slate-900 flex items-center gap-2">
          <span className="w-7 h-7 bg-brand-50 rounded-lg flex items-center justify-center">
            <IconStar />
          </span>
          AI Product Analysis
        </h3>
        <ValueBadge rating={data.value_rating} />
      </div>

      {/* Verdict */}
      <div className="bg-slate-50 rounded-xl p-4">
        <p className="text-sm font-medium text-slate-700 leading-relaxed">&ldquo;{data.verdict}&rdquo;</p>
      </div>

      {/* Who it's for */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Who it&apos;s for</p>
        <p className="text-sm text-slate-600 leading-relaxed">{data.who_its_for}</p>
      </div>

      {/* Pros & Cons */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-green-600 uppercase tracking-wider mb-2">Pros</p>
          <ul className="space-y-2">
            {data.pros.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <IconCheck />{p}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold text-red-500 uppercase tracking-wider mb-2">Cons</p>
          <ul className="space-y-2">
            {data.cons.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <IconX />{c}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Review highlights */}
      {data.review_highlights.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">What buyers say</p>
          <div className="space-y-2">
            {data.review_highlights.map((r, i) => (
              <div key={i} className="p-3 bg-slate-50 rounded-xl">
                <div className="flex items-center justify-between mb-1.5">
                  <SourceBadge source={r.source} />
                  <SentimentBadge sentiment={r.sentiment} />
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">&ldquo;{r.text}&rdquo;</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Seller analysis card — displays Claude AI trust score, strengths, and customer feedback
function SellerAnalysisCard({ data, seller }: { data: AnalyzeResponse["seller_analysis"]; seller: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-slate-900 flex items-center gap-2">
          <span className="w-7 h-7 bg-violet-50 rounded-lg flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </span>
          Seller Intelligence
        </h3>
        <TrustBadge score={data.trust_score} />
      </div>

      <p className="text-sm font-semibold text-slate-800">{seller}</p>

      {/* Verdict */}
      <div className="bg-slate-50 rounded-xl p-4">
        <p className="text-sm font-medium text-slate-700 leading-relaxed">&ldquo;{data.verdict}&rdquo;</p>
      </div>

      {/* Strengths & Watch out */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-green-600 uppercase tracking-wider mb-2">Strengths</p>
          <ul className="space-y-2">
            {data.strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <IconCheck />{s}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-2">Watch out for</p>
          <ul className="space-y-2">
            {data.watch_out_for.map((w, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <IconWarn />{w}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Shipping & Returns */}
      <div className="grid grid-cols-1 gap-3">
        <div className="flex gap-3 p-3 bg-blue-50 rounded-xl">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" className="flex-shrink-0 mt-0.5">
            <rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
          </svg>
          <div>
            <p className="text-xs font-semibold text-blue-700 mb-0.5">Shipping</p>
            <p className="text-xs text-slate-600">{data.shipping_reputation}</p>
          </div>
        </div>
        <div className="flex gap-3 p-3 bg-slate-50 rounded-xl">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" className="flex-shrink-0 mt-0.5">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.75"/>
          </svg>
          <div>
            <p className="text-xs font-semibold text-slate-600 mb-0.5">Returns</p>
            <p className="text-xs text-slate-600">{data.return_policy_note}</p>
          </div>
        </div>
      </div>

      {/* Customer feedback */}
      {data.customer_feedback.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Customer experiences</p>
          <div className="space-y-2">
            {data.customer_feedback.map((r, i) => (
              <div key={i} className="p-3 bg-slate-50 rounded-xl">
                <div className="flex items-center justify-between mb-1.5">
                  <SourceBadge source={r.source} />
                  <SentimentBadge sentiment={r.sentiment} />
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">&ldquo;{r.text}&rdquo;</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Skeleton loader — pulsing placeholder while Claude analysis is in flight ──────────────
function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 space-y-4 animate-pulse">
      <div className="h-5 bg-slate-100 rounded-lg w-40" />
      <div className="h-16 bg-slate-50 rounded-xl" />
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-4 bg-slate-100 rounded" />)}
        </div>
        <div className="space-y-2">
          {[1,2,3].map(i => <div key={i} className="h-4 bg-slate-100 rounded" />)}
        </div>
      </div>
    </div>
  );
}

// ── Price freshness helpers — flag sellers known for frequent price changes ───────────────
const DYNAMIC_PRICING_SELLERS = new Set([
  "amazon", "walmart", "target", "best buy", "bestbuy",
  "ebay", "newegg", "costco", "staples", "office depot",
]);

function isDynamicPricingSeller(seller: string): boolean {
  return DYNAMIC_PRICING_SELLERS.has(seller.toLowerCase().trim());
}

function PriceDisclaimer({ seller, source }: { seller: string; source: string }) {
  const isDynamic = isDynamicPricingSeller(seller);
  return (
    <div className="flex items-start gap-2 mt-3 p-3 rounded-xl bg-amber-50 border border-amber-100">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2" className="flex-shrink-0 mt-0.5">
        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
        <path d="M12 9v4"/><path d="M12 17h.01"/>
      </svg>
      <p className="text-xs text-amber-800 leading-relaxed">
        {isDynamic
          ? <><strong>{seller}</strong> updates prices frequently — sometimes multiple times a day. The price shown was fetched from {source === "google_shopping" ? "Google Shopping" : source} and may differ at checkout.</>
          : <>Price shown was fetched from {source === "google_shopping" ? "Google Shopping" : source} and may not reflect real-time changes. Always verify before purchasing.</>
        }
      </p>
    </div>
  );
}

// ── Right time to buy? — computes a signal from the 90-day price history ────────────────────
function BuySignal({ history, currentPrice }: { history: { day: number; price: number }[]; currentPrice: number }) {
  if (!history.length || currentPrice <= 0) return null;

  const prices = history.map(h => h.price);
  const minPrice = Math.min(...prices);
  const avgPrice = prices.reduce((s, p) => s + p, 0) / prices.length;

  // compare last 14 days vs prior 14 to detect a downward trend
  const recent = history.slice(0, 14).map(h => h.price);
  const prior = history.slice(14, 28).map(h => h.price);
  const recentAvg = recent.reduce((s, p) => s + p, 0) / (recent.length || 1);
  const priorAvg = prior.reduce((s, p) => s + p, 0) / (prior.length || 1);
  const trendingDown = priorAvg > recentAvg * 1.02;

  let label: string;
  let detail: string;
  let colorClass: string;
  let icon: string;

  if (currentPrice <= minPrice * 1.03) {
    label = "Near 90-day low";
    detail = "This is close to the lowest price we've seen in the last 3 months — good time to buy.";
    colorClass = "bg-green-50 border-green-200 text-green-800";
    icon = "✓";
  } else if (currentPrice <= avgPrice * 0.88) {
    const pct = Math.round((1 - currentPrice / avgPrice) * 100);
    label = "Good time to buy";
    detail = `Price is ${pct}% below the 90-day average.`;
    colorClass = "bg-green-50 border-green-200 text-green-800";
    icon = "✓";
  } else if (trendingDown && currentPrice >= avgPrice * 1.05) {
    label = "Price trending down";
    detail = "Price has been dropping recently — waiting a bit might save you money.";
    colorClass = "bg-amber-50 border-amber-200 text-amber-800";
    icon = "↓";
  } else if (currentPrice >= avgPrice * 1.12) {
    const pct = Math.round((currentPrice / avgPrice - 1) * 100);
    label = "Price is higher than usual";
    detail = `Currently ${pct}% above the 90-day average. Might be worth waiting for a dip.`;
    colorClass = "bg-amber-50 border-amber-200 text-amber-800";
    icon = "↑";
  } else {
    label = "Price looks typical";
    detail = "Current price is in the normal range for this product.";
    colorClass = "bg-slate-50 border-slate-200 text-slate-700";
    icon = "~";
  }

  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border ${colorClass}`}>
      <span className="text-base font-bold flex-shrink-0 w-5 text-center">{icon}</span>
      <div>
        <p className="font-semibold text-sm">{label}</p>
        <p className="text-xs mt-0.5 opacity-80 leading-relaxed">{detail}</p>
      </div>
    </div>
  );
}

// ── Other sellers from the same search — read from localStorage cache ────────────────────
function ComparisonPanel({ currentSeller, currentPrice, currentQuery }: { currentSeller: string; currentPrice: number; currentQuery: string }) {
  const [alternatives, setAlternatives] = useState<Listing[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("ss_last_results");
      if (!raw) return;
      const stored = JSON.parse(raw);
      // bail if the cache is from a completely different search
      if (currentQuery && stored.query && stored.query.toLowerCase() !== currentQuery.toLowerCase()) return;
      const all: Listing[] = [...(stored.top_picks || []), ...(stored.other_results || [])];
      const alts = all
        .filter(l =>
          l.seller_name.toLowerCase() !== currentSeller.toLowerCase() &&
          l.price > 0 &&
          currentPrice > 0 &&
          Math.abs(l.price - currentPrice) / currentPrice <= 0.45
        )
        .slice(0, 4);
      setAlternatives(alts);
    } catch {}
  }, [currentSeller, currentPrice, currentQuery]);

  if (!alternatives.length) return null;

  return (
    <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
      <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
        <span className="w-7 h-7 bg-blue-50 rounded-lg flex items-center justify-center">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </span>
        Also Available At
      </h3>
      <div className="space-y-2">
        {alternatives.map((alt) => {
          const diff = alt.price - currentPrice;
          const diffStr = diff > 0 ? `+$${diff.toFixed(2)}` : `-$${Math.abs(diff).toFixed(2)}`;
          const diffColor = diff > 0 ? "text-red-500" : "text-green-600";
          return (
            <div key={alt.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{alt.seller_name}</p>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  {alt.rating && <span className="text-xs text-slate-500">⭐ {alt.rating.toFixed(1)}</span>}
                  {alt.value_score > 0 && (
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full ${
                      alt.value_score >= 75 ? "bg-green-50 text-green-700" :
                      alt.value_score >= 55 ? "bg-blue-50 text-blue-700" :
                      "bg-amber-50 text-amber-700"
                    }`}>{alt.value_score}/100</span>
                  )}
                  {alt.condition && alt.condition !== "new" && (
                    <span className="text-xs text-purple-600 capitalize">{alt.condition.replace("_", " ")}</span>
                  )}
                </div>
              </div>
              <div className="text-right ml-4 flex-shrink-0">
                <p className="font-bold text-slate-900">${alt.price.toFixed(2)}</p>
                <p className={`text-xs font-medium ${diffColor}`}>{diffStr} vs here</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-slate-400 mt-3 leading-relaxed">
        From your search results. Prices may have changed — verify before buying.
      </p>
    </div>
  );
}

// ── Nearest local store from the search — buy today, no shipping wait ────────────────────
function LocalStoreCallout({ currentQuery }: { currentQuery: string }) {
  const [store, setStore] = useState<LocalStore | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("ss_last_results");
      if (!raw) return;
      const stored = JSON.parse(raw);
      if (currentQuery && stored.query && stored.query.toLowerCase() !== currentQuery.toLowerCase()) return;
      const stores: LocalStore[] = stored.local_stores || [];
      if (!stores.length) return;
      const nearest = [...stores].sort((a, b) => (a.distance_km ?? 999) - (b.distance_km ?? 999))[0];
      setStore(nearest);
    } catch {}
  }, [currentQuery]);

  if (!store) return null;

  const distMi = store.distance_km != null
    ? `${(store.distance_km * 0.621371).toFixed(1)} mi away`
    : "Nearby";

  return (
    <div className="bg-green-50 border border-green-100 rounded-2xl p-4 flex items-start gap-3">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" className="flex-shrink-0 mt-0.5">
        <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
      </svg>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-green-800 text-sm truncate">{store.name}</p>
        <p className="text-xs text-green-700 mt-0.5">{distMi} · Walk out with it today, no shipping wait</p>
        {store.rating && (
          <p className="text-xs text-slate-500 mt-1">⭐ {store.rating.toFixed(1)} rated</p>
        )}
      </div>
      {store.maps_url && (
        <a href={store.maps_url} target="_blank" rel="noopener noreferrer"
          className="text-xs text-green-700 font-semibold hover:underline flex-shrink-0 mt-0.5">
          Directions ↗
        </a>
      )}
    </div>
  );
}

// ── Main page — reads product params from the URL, calls /api/v1/analyze, and renders all cards ──
function ProductContent() {
  const params = useSearchParams();
  const title  = params.get("title")  || "Product";
  const price  = Number(params.get("price")) || 0;
  const seller = params.get("seller") || "Seller";
  const url    = params.get("url")    || "#";
  const source = params.get("source") || "";
  const query  = params.get("q")      || "";

  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Prefer the direct product page resolved by the backend; fall back to the original URL from search
  const bestUrl = data?.direct_url || url;

  useEffect(() => {
    if (!title || !seller) return;
    setLoading(true);
    analyzeProduct({ title, seller, price, source, url })
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [title, seller, price, source, url]);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white border-b border-slate-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center gap-4">
          <Link
            href={`/results?q=${encodeURIComponent(query)}`}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-700 transition-colors text-sm font-medium"
          >
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
        {/* Status bar */}
        <div className="mb-6 flex items-center gap-3 text-sm bg-white border border-slate-100 rounded-xl px-4 py-3">
          {loading ? (
            <>
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="w-2 h-2 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
              <span className="text-slate-500">Running AI analysis — gathering reviews, estimating price, analyzing seller...</span>
            </>
          ) : error ? (
            <span className="text-red-500 flex items-center gap-2"><IconX /> Analysis unavailable — showing basic info</span>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
              <span className="text-slate-600 font-medium">Analysis complete — powered by Claude AI</span>
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── Left column (2/3): product header, price breakdown, chart, AI analysis cards ── */}
          <div className="lg:col-span-2 space-y-6">
            {/* Product header: title, seller, listed price, and price-freshness disclaimer */}
            <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
              <div className="flex gap-4">
                <div className="w-24 h-24 bg-gradient-to-br from-slate-100 to-slate-200 rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <h1 className="text-xl font-bold text-slate-900 leading-snug">{title}</h1>
                  <p className="text-slate-500 text-sm mt-1">
                    Sold by <span className="font-medium text-slate-700">{seller}</span>
                    {source && <span className="ml-2 text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full capitalize">{source}</span>}
                  </p>
                  {price > 0 && (
                    <div className="mt-3">
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-extrabold text-slate-900">${price.toFixed(2)}</span>
                        <span className="text-sm text-slate-400">listed price</span>
                      </div>
                      <PriceDisclaimer seller={seller} source={source} />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Price breakdown card: listed → estimated shipping + fees → final total */}
            {loading && <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 animate-pulse space-y-3">
              <div className="h-5 bg-slate-100 rounded w-32" />
              {[1,2,3,4].map(i => <div key={i} className="h-4 bg-slate-100 rounded" />)}
            </div>}
            {data && <PriceBreakdown data={data.price} />}

            {/* 90-day price history area chart */}
            {data && <PriceHistoryChart history={data.price.price_history} currentPrice={price} />}

            {/* right time to buy signal — computed from price history */}
            {data && <BuySignal history={data.price.price_history} currentPrice={price} />}

            {/* Claude AI product analysis: verdict, pros/cons, who it's for, review highlights */}
            {loading && <SkeletonCard />}
            {data && <ProductAnalysisCard data={data.product_analysis} />}

            {/* Claude AI seller analysis: trust score, strengths, watch-outs, shipping & returns */}
            {loading && <SkeletonCard />}
            {data && <SellerAnalysisCard data={data.seller_analysis} seller={seller} />}

            {/* other sellers carrying the same product from the search results */}
            <ComparisonPanel currentSeller={seller} currentPrice={price} currentQuery={query} />
          </div>

          {/* ── Right column (1/3): CTA button, price alert, quick stats, AI disclaimer ── */}
          <div className="space-y-4">
            {/* Primary CTA: deep link to the exact product page, or a Google search fallback */}
            {bestUrl && bestUrl !== "#" ? (() => {
              const isGoogleSearch = bestUrl.includes("google.com/search");
              return (
                <div className="space-y-2">
                  <a
                    href={bestUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 py-4 text-base font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-2xl transition-colors shadow-sm"
                  >
                    {isGoogleSearch ? `Find on Google` : `Go to ${source === "ebay" ? "eBay" : seller}`}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                      <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </a>
                  {isGoogleSearch && (
                    <p className="text-xs text-center text-slate-400">
                      Google will show the direct product page on {seller}&apos;s site
                    </p>
                  )}
                  {!isGoogleSearch && data?.direct_url && (
                    <p className="text-xs text-center text-green-600 font-medium">
                      Direct link found
                    </p>
                  )}
                  <p className="text-xs text-center text-slate-400 mt-1">
                    Prices may have changed — verify at checkout
                  </p>
                </div>
              );
            })() : (
              <div className="w-full flex items-center justify-center gap-2 py-4 text-base font-semibold text-slate-600 bg-slate-100 rounded-2xl">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                </svg>
                Visit in store
              </div>
            )}

            {/* nearest local store — walk out with it today */}
            <LocalStoreCallout currentQuery={query} />

            {/* Price drop alert widget — only shown when a real price is available */}
            {price > 0 && <PriceAlert price={price} productTitle={title} seller={seller} />}

            {/* Quick stats panel: seller name, platform, trust level, value rating, extra fees */}
            <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-5">
              <h3 className="font-bold text-slate-900 mb-3 text-sm">Quick Stats</h3>
              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Seller</span>
                  <span className="font-medium text-slate-800 truncate max-w-[120px]">{seller}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Platform</span>
                  <span className="font-medium text-slate-800 capitalize">{source || "Online"}</span>
                </div>
                {data && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Trust level</span>
                      <span className={`font-medium capitalize ${
                        data.seller_analysis.trust_score === "high" ? "text-green-600" :
                        data.seller_analysis.trust_score === "medium" ? "text-amber-600" :
                        "text-red-600"
                      }`}>{data.seller_analysis.trust_score}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Value rating</span>
                      <span className={`font-medium capitalize ${
                        data.product_analysis.value_rating === "excellent" ? "text-green-600" :
                        data.product_analysis.value_rating === "good" ? "text-blue-600" :
                        data.product_analysis.value_rating === "fair" ? "text-amber-600" :
                        "text-red-600"
                      }`}>{data.product_analysis.value_rating}</span>
                    </div>
                    <div className="h-px bg-slate-100" />
                    <div className="flex justify-between">
                      <span className="text-slate-500">Extra fees est.</span>
                      <span className="font-medium text-slate-800">+${data.price.savings_vs_estimate.toFixed(2)}</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Disclosure notice reminding users that analysis is AI-generated */}
            <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4">
              <p className="text-xs text-amber-700 leading-relaxed">
                <span className="font-semibold">AI-powered analysis.</span> Summaries are generated by Claude AI based on publicly available reviews. Always verify before purchasing.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProductPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-50 animate-pulse" />}>
      <ProductContent />
    </Suspense>
  );
}

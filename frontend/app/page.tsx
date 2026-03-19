import SearchBar from "@/components/SearchBar";

const POPULAR = ["iPhone 15 Pro", "Sony WH-1000XM5", "Nike Air Max", "MacBook Air M3", "PlayStation 5"];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Hero section: gradient background, headline, search bar, and popular search chips */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 hero-glow pointer-events-none" />
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-bl from-violet-100/60 to-transparent rounded-full -translate-y-1/2 translate-x-1/4 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-to-tr from-indigo-100/40 to-transparent rounded-full translate-y-1/2 -translate-x-1/4 pointer-events-none" />

        <div className="relative max-w-4xl mx-auto px-6 pt-24 pb-20 flex flex-col items-center text-center">
          {/* 'AI-Powered' badge pill above the headline */}
          <div className="inline-flex items-center gap-2 bg-brand-50 text-brand-700 text-sm font-semibold px-4 py-2 rounded-full border border-brand-100 mb-8">
            <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            AI-Powered Price Intelligence
          </div>

          {/* Main headline with gradient accent on 'anywhere' */}
          <h1 className="text-5xl sm:text-6xl font-extrabold text-slate-900 tracking-tight leading-tight mb-6">
            Find the best price{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-600 to-violet-600">
              anywhere
            </span>
          </h1>

          <p className="text-xl text-slate-500 max-w-xl mb-12 leading-relaxed">
            Search across Amazon, eBay, local shops, and hundreds of niche sellers.
            Our AI predicts the real final price — no checkout surprises.
          </p>

          {/* Search bar component — handles GPS + city input internally */}
          <div className="w-full max-w-xl">
            <SearchBar />
          </div>

          {/* Quick-search chip links for common product categories */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            <span className="text-sm text-slate-400 mr-1">Popular:</span>
            {POPULAR.map((term) => (
              <a
                key={term}
                href={`/results?q=${encodeURIComponent(term)}`}
                className="text-sm text-slate-600 bg-slate-100 hover:bg-brand-50 hover:text-brand-700 px-3 py-1.5 rounded-full transition-colors border border-transparent hover:border-brand-200"
              >
                {term}
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Feature cards: three value props explaining what ShopSmart does */}
      <div className="max-w-5xl mx-auto px-6 py-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-brand-600">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
              ),
              title: "Search everywhere",
              desc: "We search Amazon, eBay, local shops, and niche sellers simultaneously — places Google Shopping misses.",
              color: "bg-brand-50",
            },
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-violet-600">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                </svg>
              ),
              title: "Real final price",
              desc: "Our ML model predicts shipping fees, hidden charges, and taxes before you commit to buying.",
              color: "bg-violet-50",
            },
            {
              icon: (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-pink-600">
                  <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>
                </svg>
              ),
              title: "Find it nearby",
              desc: "See which local stores carry your product on an interactive map. Buy today, skip the shipping wait.",
              color: "bg-pink-50",
            },
          ].map((f) => (
            <div key={f.title} className="card p-6 hover:-translate-y-1 transition-transform duration-300">
              <div className={`w-14 h-14 ${f.color} rounded-2xl flex items-center justify-center mb-4`}>
                {f.icon}
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">{f.title}</h3>
              <p className="text-slate-500 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Minimal footer with copyright */}
      <footer className="border-t border-slate-100 py-8 text-center text-sm text-slate-400">
        © 2026 ShopSmart · Built with AI
      </footer>
    </main>
  );
}

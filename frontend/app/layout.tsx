import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "ShopSmart — Find the Best Price Anywhere",
  description: "Discover products from local shops, Amazon, eBay and more. Get AI-powered price predictions and real user reviews.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased bg-white text-slate-900">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

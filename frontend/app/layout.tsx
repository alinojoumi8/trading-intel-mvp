import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SidebarWrapper } from "@/components/SidebarWrapper";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || "https://trading-intel.example.com";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "Trading Intelligence",
    template: "%s | Trading Intelligence",
  },
  description: "AI-generated trade briefings, setups, and macro analysis for active traders. Curated market intelligence for forex, commodities, crypto, and indices.",
  keywords: ["trading", "forex", "gold", "bitcoin", "trade setups", "market analysis", "macro", "trading intelligence"],
  authors: [{ name: "Trading Intelligence" }],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: BASE_URL,
    siteName: "Trading Intelligence",
    title: "Trading Intelligence",
    description: "AI-generated trade briefings, setups, and macro analysis for active traders.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Trading Intelligence",
    description: "AI-generated trade briefings, setups, and macro analysis for active traders.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: BASE_URL,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen antialiased bg-black`}>
        <div className="flex min-h-screen">
          <SidebarWrapper />
          <div className="flex-1 flex flex-col min-h-screen bg-zinc-950">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

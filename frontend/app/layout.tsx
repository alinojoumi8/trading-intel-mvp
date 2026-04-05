import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

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
    default: "SignaLayer.ai — AI Trading Intelligence",
    template: "%s | SignaLayer.ai",
  },
  description: "AI-powered market intelligence for retail traders. Trade setups, morning briefings, macro analysis, and real-time signals.",
  keywords: ["trading", "forex", "gold", "bitcoin", "trade setups", "market analysis", "macro", "trading intelligence", "AI trading"],
  authors: [{ name: "SignaLayer.ai" }],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: BASE_URL,
    siteName: "SignaLayer.ai",
    title: "SignaLayer.ai — AI Trading Intelligence",
    description: "AI-powered market intelligence for retail traders.",
  },
  twitter: {
    card: "summary_large_image",
    title: "SignaLayer.ai — AI Trading Intelligence",
    description: "AI-powered market intelligence for retail traders.",
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
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen antialiased bg-[#09090B]`}>
        {children}
      </body>
    </html>
  );
}

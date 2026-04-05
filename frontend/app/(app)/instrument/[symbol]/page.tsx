import { Metadata } from "next";
import InstrumentPageContent from "./InstrumentPageContent";

export const dynamic = "force-dynamic";

// Dynamic metadata for instrument pages
export async function generateMetadata({
  params,
}: {
  params: Promise<{ symbol: string }>;
}): Promise<Metadata> {
  const { symbol } = await params;
  const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || "https://trading-intel.example.com";

  return {
    title: `${symbol} - Trading Intelligence`,
    description: `Trade setups, briefings, and analysis for ${symbol}. AI-generated trading intelligence with entry zones, stop-loss, and take-profit levels.`,
    openGraph: {
      title: `${symbol} | Trading Intelligence`,
      description: `Trade setups, briefings, and analysis for ${symbol}. AI-generated trading intelligence.`,
      url: `${BASE_URL}/instrument/${symbol}`,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: `${symbol} | Trading Intelligence`,
      description: `Trade setups, briefings, and analysis for ${symbol}.`,
    },
    alternates: {
      canonical: `${BASE_URL}/instrument/${symbol}`,
    },
  };
}

export default InstrumentPageContent;

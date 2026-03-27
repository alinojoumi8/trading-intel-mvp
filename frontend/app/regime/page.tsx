import { Metadata } from "next";
import RegimePageContent from "./RegimePageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Market Regime - Trading Intelligence",
  description: "Real-time market regime detection and volatility analysis for major forex pairs, commodities, and crypto.",
};

export default RegimePageContent;

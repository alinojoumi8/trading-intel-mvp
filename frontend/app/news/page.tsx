import { Metadata } from "next";
import NewsPageContent from "./NewsPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "News Feed - Trading Intelligence",
  description: "Real-time market news aggregated from 130+ RSS sources across Forex, Crypto, Commodities, and more.",
};

export default NewsPageContent;

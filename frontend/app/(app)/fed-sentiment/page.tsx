import { Metadata } from "next";
import FedSentimentPageContent from "./FedSentimentPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fed Sentiment - Trading Intelligence",
  description: "Federal Reserve hawkish/dovish composite score, market-implied expectations, and divergence signal",
};

export default FedSentimentPageContent;

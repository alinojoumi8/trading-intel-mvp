import { Metadata } from "next";
import COTHistoryPageContent from "./COTHistoryPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "COT History - Trading Intelligence",
  description: "Commitment of Traders historical data for GOLD, EUR, GBP, JPY, OIL",
};

export default COTHistoryPageContent;

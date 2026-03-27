import { Metadata } from "next";
import PerformancePageContent from "./PerformancePageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Performance - Trading Intelligence",
  description: "Trade setup performance statistics and win rate analysis",
};

export default PerformancePageContent;

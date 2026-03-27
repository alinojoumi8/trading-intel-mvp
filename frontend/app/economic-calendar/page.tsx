import { Metadata } from "next";
import EconomicCalendarPageContent from "./EconomicCalendarPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Economic Calendar - Trading Intelligence",
  description: "Upcoming economic events that impact markets - FOMC, NFP, CPI, GDP, central bank decisions and more.",
};

export default EconomicCalendarPageContent;

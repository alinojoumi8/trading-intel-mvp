import { Metadata } from "next";
import BriefingPageContent from "./BriefingPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Morning Briefing — Trading Intelligence",
  description: "AI-powered morning market briefing with key levels, signals, and macro events",
};

export default BriefingPageContent;

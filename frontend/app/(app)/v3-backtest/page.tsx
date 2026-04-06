import { Metadata } from "next";
import V3BacktestPageContent from "./V3BacktestPageContent";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "V3 Backtest - Trading Intelligence",
  description: "Historical V3 trading signal pipeline backtest results — win rate, equity curve, per-trade detail",
};

export default V3BacktestPageContent;

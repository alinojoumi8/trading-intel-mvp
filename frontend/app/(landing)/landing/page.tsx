"use client";

import { useEffect, useState, useRef } from "react";

const ACCENT = "#00FF41";
const BG = "#09090B";

// ─── Animated Counter ────────────────────────────────────────────────────────

function AnimatedCounter({
  end,
  suffix = "",
  prefix = "",
  duration = 2000,
  color = ACCENT,
}: {
  end: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
  color?: string;
}) {
  const [count, setCount] = useState(0);
  const [started, setStarted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started) setStarted(true);
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [started]);

  useEffect(() => {
    if (!started) return;
    let startTime: number;
    let frame: number;
    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setCount(Math.floor(eased * end));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [started, end, duration]);

  return (
    <div ref={ref} className="text-3xl sm:text-4xl font-bold mb-1 tabular-nums" style={{ color }}>
      {prefix}
      {count.toLocaleString()}
      {suffix}
    </div>
  );
}

// ─── Ticker Tape ─────────────────────────────────────────────────────────────

const TICKER_ITEMS = [
  { symbol: "EURUSD", price: "1.0847", change: "+0.12%" },
  { symbol: "XAUUSD", price: "2,348.50", change: "+1.24%" },
  { symbol: "BTC/USD", price: "84,230", change: "+2.87%" },
  { symbol: "SPX", price: "5,248.30", change: "-0.31%" },
  { symbol: "GBP/USD", price: "1.2634", change: "+0.08%" },
  { symbol: "WTI", price: "83.42", change: "-1.15%" },
  { symbol: "USD/JPY", price: "151.82", change: "+0.45%" },
  { symbol: "COPPER", price: "4.523", change: "+0.67%" },
  { symbol: "DAX", price: "18,432", change: "+0.93%" },
  { symbol: "VIX", price: "13.24", change: "-2.10%" },
];

function TickerTape() {
  return (
    <div className="overflow-hidden border-y border-zinc-800/60 bg-zinc-950/50">
      <div className="flex animate-ticker whitespace-nowrap py-2">
        {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
          <div key={i} className="inline-flex items-center gap-2 mx-6 text-xs font-mono">
            <span className="text-zinc-400 font-semibold">{item.symbol}</span>
            <span className="text-zinc-300">{item.price}</span>
            <span
              className={
                item.change.startsWith("+") ? "text-green-400" : "text-red-400"
              }
            >
              {item.change}
            </span>
          </div>
        ))}
      </div>
      <style jsx>{`
        @keyframes ticker {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        .animate-ticker {
          animation: ticker 30s linear infinite;
        }
      `}</style>
    </div>
  );
}

// ─── Pulsing Dot ─────────────────────────────────────────────────────────────

function PulsingDot() {
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span
        className="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping"
        style={{ backgroundColor: ACCENT }}
      ></span>
      <span
        className="relative inline-flex h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: ACCENT }}
      ></span>
    </span>
  );
}

// ─── Signal Preview Card ─────────────────────────────────────────────────────

function SignalPreview({
  instrument,
  type,
  direction,
  entry,
  target,
  stop,
  confidence,
  timeAgo,
}: {
  instrument: string;
  type: string;
  direction: "LONG" | "SHORT";
  entry: string;
  target: string;
  stop: string;
  confidence: number;
  timeAgo: string;
}) {
  const isLong = direction === "LONG";
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 hover:border-zinc-700 transition-all">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold text-sm">{instrument}</span>
          <span
            className={`text-xs px-2 py-0.5 rounded font-medium ${
              isLong
                ? "bg-green-900/40 text-green-400 border border-green-800"
                : "bg-red-900/40 text-red-400 border border-red-800"
            }`}
          >
            {type}
          </span>
        </div>
        <span className="text-zinc-500 text-xs font-mono">{timeAgo}</span>
      </div>
      <div className="flex items-center gap-4 mb-3">
        <span
          className={`text-lg font-bold ${
            isLong ? "text-green-400" : "text-red-400"
          }`}
        >
          {direction}
        </span>
        <div className="flex gap-4 text-xs font-mono">
          <div>
            <span className="text-zinc-500 block">ENTRY</span>
            <span className="text-zinc-200">{entry}</span>
          </div>
          <div>
            <span className="text-zinc-500 block">TARGET</span>
            <span className="text-green-400">{target}</span>
          </div>
          <div>
            <span className="text-zinc-500 block">STOP</span>
            <span className="text-red-400">{stop}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-zinc-500 text-xs">Confidence</span>
          <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${confidence}%`,
                backgroundColor:
                  confidence >= 80
                    ? ACCENT
                    : confidence >= 60
                    ? "#facc15"
                    : "#ef4444",
              }}
            />
          </div>
          <span className="text-zinc-300 text-xs font-mono">{confidence}%</span>
        </div>
      </div>
    </div>
  );
}

// ─── Pipeline Stage Icon ─────────────────────────────────────────────────────

function PipelineStage({
  number,
  title,
  description,
  icon,
}: {
  number: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="relative group">
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 hover:border-zinc-700 transition-all h-full">
        <div className="flex items-start gap-4">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${ACCENT}10`, color: ACCENT }}
          >
            {icon}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-xs font-mono px-2 py-0.5 rounded"
                style={{ backgroundColor: `${ACCENT}15`, color: ACCENT }}
              >
                Stage {number}
              </span>
            </div>
            <h3 className="text-white font-semibold text-base mb-1">{title}</h3>
            <p className="text-zinc-400 text-sm leading-relaxed">
              {description}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Check / X Icons ─────────────────────────────────────────────────────────

function CheckIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 20 20" fill={ACCENT}>
      <path
        fillRule="evenodd"
        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0 text-zinc-600" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ─── Feature Row ──────────────────────────────────────────────────────────────

function FeatureRow({
  feature,
  free,
  pro,
}: {
  feature: string;
  free: boolean | string;
  pro: boolean | string;
}) {
  return (
    <tr className="border-b border-zinc-800/60 last:border-0">
      <td className="py-4 pr-4 text-zinc-300 text-sm">{feature}</td>
      <td className="py-4 px-4 text-center">
        {typeof free === "boolean" ? (
          free ? (
            <CheckIcon />
          ) : (
            <XIcon />
          )
        ) : (
          <span className="text-xs font-mono text-zinc-500">{free}</span>
        )}
      </td>
      <td className="py-4 pl-4 text-center">
        {typeof pro === "boolean" ? (
          pro ? (
            <CheckIcon />
          ) : (
            <XIcon />
          )
        ) : (
          <span className="text-xs font-mono" style={{ color: ACCENT }}>
            {pro}
          </span>
        )}
      </td>
    </tr>
  );
}

// ─── Logo SVG ────────────────────────────────────────────────────────────────

function Logo() {
  return (
    <svg
      width="180"
      height="36"
      viewBox="0 0 180 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="translate(0, 4)">
        <path
          d="M4 20 Q8 12 12 20"
          stroke={ACCENT}
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M10 14 Q16 4 22 14"
          stroke={ACCENT}
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M18 8 Q26 -2 34 8"
          stroke={ACCENT}
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        <circle cx="4" cy="20" r="2.5" fill={ACCENT} />
      </g>
      <text
        x="44"
        y="26"
        fontFamily="Arial, sans-serif"
        fontSize="20"
        fontWeight="bold"
        fill="white"
      >
        Signa
      </text>
      <text
        x="113"
        y="26"
        fontFamily="Arial, sans-serif"
        fontSize="20"
        fontWeight="bold"
        fill={ACCENT}
      >
        Layer
      </text>
      <text
        x="162"
        y="26"
        fontFamily="Arial, sans-serif"
        fontSize="14"
        fontWeight="bold"
        fill={ACCENT}
      >
        .ai
      </text>
    </svg>
  );
}

// ─── Main Landing Page ───────────────────────────────────────────────────────

export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleStartFree = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setSubmitted(true);
  };

  const features = [
    { feature: "Real-Time News Feed (130+ Sources)", free: true, pro: true },
    { feature: "AI Trade Setups", free: "3/day", pro: "Unlimited" },
    { feature: "Daily Morning Briefings", free: true, pro: true },
    { feature: "Weekly Macro Roundups", free: false, pro: true },
    { feature: "Contrarian Alerts", free: false, pro: true },
    { feature: "6-Stage AI Trading Signals", free: false, pro: true },
    { feature: "Multi-Timeframe Analysis", free: false, pro: true },
    { feature: "COT Report Analysis", free: false, pro: true },
    { feature: "Economic Calendar", free: false, pro: true },
    { feature: "Market Regime Dashboard", free: false, pro: true },
    { feature: "Asset Correlation Matrix", free: false, pro: true },
    { feature: "Signal History", free: "7 days", pro: "Unlimited" },
  ];

  return (
    <div style={{ backgroundColor: BG }} className="min-h-screen text-white font-sans">
      {/* ─── Navigation ───────────────────────────────────────────────────── */}
      <nav className="border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Logo />
            <div className="hidden md:flex items-center gap-8">
              <a
                href="#features"
                className="text-zinc-400 hover:text-white text-sm transition-colors"
              >
                Features
              </a>
              <a
                href="#pipeline"
                className="text-zinc-400 hover:text-white text-sm transition-colors"
              >
                AI Pipeline
              </a>
              <a
                href="#how-it-works"
                className="text-zinc-400 hover:text-white text-sm transition-colors"
              >
                How It Works
              </a>
              <a
                href="#pricing"
                className="text-zinc-400 hover:text-white text-sm transition-colors"
              >
                Pricing
              </a>
            </div>
            <div className="flex items-center gap-3">
              <a
                href="/auth/login"
                className="hidden sm:block text-zinc-400 hover:text-white text-sm transition-colors"
              >
                Sign In
              </a>
              <a
                href="#pricing"
                className="px-4 py-2 rounded-lg text-sm font-medium transition-all hover:opacity-90"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                Get Started
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* ─── Ticker Tape ──────────────────────────────────────────────────── */}
      <TickerTape />

      {/* ─── Hero Section ─────────────────────────────────────────────────── */}
      <section className="py-20 md:py-28 px-4 relative overflow-hidden">
        {/* Background gradient */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            background: `radial-gradient(ellipse 60% 50% at 50% 0%, ${ACCENT}20, transparent)`,
          }}
        />

        <div className="max-w-6xl mx-auto relative">
          <div className="text-center mb-12">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-900 border border-zinc-800 mb-8">
              <PulsingDot />
              <span className="text-sm font-mono text-zinc-400">
                AI-Powered Market Intelligence
              </span>
            </div>

            <h1 className="text-4xl sm:text-5xl md:text-7xl font-bold tracking-tight mb-6 leading-tight">
              Stop Guessing.
              <br />
              Start{" "}
              <span style={{ color: ACCENT }}>Trading with an Edge.</span>
            </h1>

            <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 leading-relaxed">
              Our AI scans thousands of data points across macro fundamentals,
              positioning, price action, and news — then delivers actionable trade
              setups, daily briefings, and real-time alerts straight to your
              dashboard.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
              <a
                href="#pricing"
                className="w-full sm:w-auto px-8 py-4 rounded-xl text-base font-semibold transition-all hover:scale-105"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                Start Free — No Card Required
              </a>
              <a
                href="#pipeline"
                className="w-full sm:w-auto px-8 py-4 rounded-xl text-base font-semibold border border-zinc-700 hover:border-zinc-500 transition-all hover:scale-105"
              >
                See How It Works
              </a>
            </div>

            <p className="text-zinc-500 text-sm">
              Trusted by 12,000+ retail traders · 85% signal accuracy · 24/7
              market coverage
            </p>
          </div>

          {/* Signal previews */}
          <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
            <SignalPreview
              instrument="XAUUSD"
              type="Trade Setup"
              direction="LONG"
              entry="$2,340 – $2,348"
              target="$2,390"
              stop="$2,320"
              confidence={87}
              timeAgo="2h ago"
            />
            <SignalPreview
              instrument="EUR/USD"
              type="Signal"
              direction="SHORT"
              entry="1.0860 – 1.0875"
              target="1.0780"
              stop="1.0910"
              confidence={79}
              timeAgo="4h ago"
            />
            <SignalPreview
              instrument="BTC/USD"
              type="Contrarian Alert"
              direction="LONG"
              entry="$82,500 – $83,800"
              target="$88,000"
              stop="$80,200"
              confidence={72}
              timeAgo="6h ago"
            />
            <SignalPreview
              instrument="WTI"
              type="Trade Setup"
              direction="SHORT"
              entry="$83.80 – $84.50"
              target="$80.20"
              stop="$85.80"
              confidence={83}
              timeAgo="8h ago"
            />
          </div>
        </div>
      </section>

      {/* ─── Social Proof / Stats ─────────────────────────────────────────── */}
      <section className="py-16 border-y border-zinc-800/60">
        <div className="max-w-5xl mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
            <div className="text-center">
              <AnimatedCounter end={50} suffix="K+" color={ACCENT} />
              <div className="text-sm text-zinc-500">AI-Generated Signals</div>
            </div>
            <div className="text-center">
              <AnimatedCounter end={12} suffix="K+" color={ACCENT} />
              <div className="text-sm text-zinc-500">Active Traders</div>
            </div>
            <div className="text-center">
              <AnimatedCounter end={85} suffix="%" color={ACCENT} />
              <div className="text-sm text-zinc-500">Signal Accuracy Rate</div>
            </div>
            <div className="text-center">
              <div
                className="text-3xl sm:text-4xl font-bold mb-1"
                style={{ color: ACCENT }}
              >
                130+
              </div>
              <div className="text-sm text-zinc-500">
                News Sources Monitored
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Features Comparison ──────────────────────────────────────────── */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything You Need to{" "}
              <span style={{ color: ACCENT }}>Trade Smarter</span>
            </h2>
            <p className="text-zinc-400 max-w-xl mx-auto">
              From real-time news to AI-generated trade setups with entry zones,
              targets, and confidence scores — all in one dashboard.
            </p>
          </div>

          <div className="rounded-2xl border border-zinc-800 overflow-hidden bg-zinc-900/30">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[500px]">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left py-4 px-6 font-semibold text-zinc-400 text-sm">
                      Feature
                    </th>
                    <th className="text-center py-4 px-4 font-semibold text-sm w-32">
                      <span className="text-zinc-300">Free</span>
                    </th>
                    <th className="text-center py-4 px-4 font-semibold text-sm w-32">
                      <span style={{ color: ACCENT }}>Pro</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((f) => (
                    <FeatureRow
                      key={f.feature}
                      feature={f.feature}
                      free={f.free}
                      pro={f.pro}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* ─── AI Pipeline Section ──────────────────────────────────────────── */}
      <section
        id="pipeline"
        className="py-20 px-4 border-y border-zinc-800/60"
      >
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono mb-4"
              style={{ backgroundColor: `${ACCENT}10`, color: ACCENT }}
            >
              6-STAGE AI PIPELINE
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Professional-Grade Analysis,{" "}
              <span style={{ color: ACCENT }}>Automated</span>
            </h2>
            <p className="text-zinc-400 max-w-2xl mx-auto">
              Each signal passes through a rigorous 6-stage analysis pipeline
              modeled after professional macro trading desks. Every stage chains
              into the next — just like a human analyst would.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <PipelineStage
              number="0"
              title="Asset Pre-Screen"
              description="Confirms the asset is tradeable — floating regime, meaningful volatility, acceptable spread cost. Rejects dead or pegged markets."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M9 12l2 2 4-4" />
                  <circle cx="12" cy="12" r="10" />
                </svg>
              }
            />
            <PipelineStage
              number="1"
              title="Market Regime Classifier"
              description="Classifies Bull/Bear market and VIX volatility regime. Determines position sizing: Portfolio Manager → Day Trader → Sidelines."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              }
            />
            <PipelineStage
              number="2"
              title="Growth/Inflation Grid"
              description="4-Quadrant framework: Expansion, Reflation, Disinflation, Stagflation. Uses rate-of-change logic, not absolute levels."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                </svg>
              }
            />
            <PipelineStage
              number="3"
              title="Asset-Class Deep Dive"
              description="3-Step Analysis: Baseline expectations → Surprise scenarios → Bigger picture impact. Covers FX, Equities, Commodities, Bonds."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              }
            />
            <PipelineStage
              number="4"
              title="Gatekeeping"
              description="COT positioning + IV ranges + 14-Point Technical Traffic Light. Determines WHEN and HOW MUCH to deploy — not direction."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              }
            />
            <PipelineStage
              number="5"
              title="Signal Aggregator"
              description="Combines all 6 stages into a final trade plan: direction, entry zone, stop loss, take profit, confidence score, and detailed rationale."
              icon={
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              }
            />
          </div>
        </div>
      </section>

      {/* ─── How It Works ─────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Three Steps to{" "}
              <span style={{ color: ACCENT }}>Smarter Trading</span>
            </h2>
            <p className="text-zinc-400">
              From sign-up to actionable signals in under 2 minutes.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-4">
            {/* Step 1 */}
            <div className="text-center p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800 relative">
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-4 relative">
                  <div
                    className="absolute -top-3 -left-3 w-8 h-8 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: BG,
                      border: "1px solid #3f3f46",
                    }}
                  >
                    <span
                      className="text-xs font-mono font-bold"
                      style={{ color: ACCENT }}
                    >
                      01
                    </span>
                  </div>
                  <svg
                    width="28"
                    height="28"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M7 22V12a5 5 0 0110 0v10" />
                    <path d="M12 12V2" />
                    <path d="M2 12h4" />
                    <path d="M18 12h4" />
                    <circle cx="12" cy="7" r="2" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold mb-2">Connect</h3>
                <p className="text-sm text-zinc-400">
                  Choose your markets and trading style. Our AI adapts to your
                  preferences instantly.
                </p>
              </div>
              <div className="hidden md:block absolute top-12 right-0 translate-x-1/2 z-10">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#27272a"
                  strokeWidth="2"
                >
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </div>
            </div>

            {/* Step 2 */}
            <div className="text-center p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800 relative">
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-4 relative">
                  <div
                    className="absolute -top-3 -left-3 w-8 h-8 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: BG,
                      border: "1px solid #3f3f46",
                    }}
                  >
                    <span
                      className="text-xs font-mono font-bold"
                      style={{ color: ACCENT }}
                    >
                      02
                    </span>
                  </div>
                  <svg
                    width="28"
                    height="28"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="22 6 13 15 9 11 2 18" />
                    <polyline points="15 6 22 6 22 13" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold mb-2">Analyze</h3>
                <p className="text-sm text-zinc-400">
                  Our AI scans thousands of data points across news, macro
                  trends, COT positioning, and price action.
                </p>
              </div>
              <div className="hidden md:block absolute top-12 right-0 translate-x-1/2 z-10">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#27272a"
                  strokeWidth="2"
                >
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </div>
            </div>

            {/* Step 3 */}
            <div className="text-center p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800">
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-4 relative">
                  <div
                    className="absolute -top-3 -left-3 w-8 h-8 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: BG,
                      border: "1px solid #3f3f46",
                    }}
                  >
                    <span
                      className="text-xs font-mono font-bold"
                      style={{ color: ACCENT }}
                    >
                      03
                    </span>
                  </div>
                  <svg
                    width="28"
                    height="28"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="12" y1="1" x2="12" y2="23" />
                    <path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold mb-2">Profit</h3>
                <p className="text-sm text-zinc-400">
                  Receive actionable trade setups with entry zones, targets,
                  stops, and confidence scores — in real-time.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Content Types Showcase ────────────────────────────────────────── */}
      <section className="py-20 px-4 border-y border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Intelligence That{" "}
              <span style={{ color: ACCENT }}>Never Sleeps</span>
            </h2>
            <p className="text-zinc-400 max-w-xl mx-auto">
              Four types of AI-generated content, each designed for a specific
              trading need.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Morning Briefing */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 hover:border-zinc-700 transition-all group">
              <div className="flex items-start gap-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: "#3b82f615" }}
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="2"
                  >
                    <path d="M12 3v1m0 16v1m-9-9h1m16 0h1m-2.636-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.343l-.707-.707" />
                    <circle cx="12" cy="12" r="4" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-semibold text-lg mb-1 group-hover:text-zinc-100">
                    Morning Briefing
                  </h3>
                  <p className="text-zinc-400 text-sm mb-3">
                    Daily at 06:00 UTC — Market mover summary, key levels,
                    risk-on/risk-off bias, and the day&apos;s catalysts. Your
                    pre-market ritual.
                  </p>
                  <span className="text-xs font-mono text-zinc-500">
                    Frequency: Daily · Free Tier Included
                  </span>
                </div>
              </div>
            </div>

            {/* Trade Setup */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 hover:border-zinc-700 transition-all group">
              <div className="flex items-start gap-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${ACCENT}10` }}
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth="2"
                  >
                    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                    <polyline points="17 6 23 6 23 12" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-semibold text-lg mb-1 group-hover:text-zinc-100">
                    Trade Setups
                  </h3>
                  <p className="text-zinc-400 text-sm mb-3">
                    Entry zone, stop loss, take profit, risk:reward ratio,
                    confidence score, and detailed rationale. 2-5 per day across
                    all major instruments.
                  </p>
                  <span className="text-xs font-mono text-zinc-500">
                    Frequency: 2-5× daily · 3/day free
                  </span>
                </div>
              </div>
            </div>

            {/* Macro Roundup */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 hover:border-zinc-700 transition-all group">
              <div className="flex items-start gap-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: "#f9731615" }}
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#f97316"
                    strokeWidth="2"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-semibold text-lg mb-1 group-hover:text-zinc-100">
                    Macro Roundup
                  </h3>
                  <p className="text-zinc-400 text-sm mb-3">
                    Weekly Friday edition — Top macro events, COT analysis,
                    yield curve signals, and the week ahead. The big picture
                    view.
                  </p>
                  <span className="text-xs font-mono text-zinc-500">
                    Frequency: Weekly (Friday) · Pro Only
                  </span>
                </div>
              </div>
            </div>

            {/* Contrarian Alert */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 hover:border-zinc-700 transition-all group">
              <div className="flex items-start gap-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: "#ef444415" }}
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="2"
                  >
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-white font-semibold text-lg mb-1 group-hover:text-zinc-100">
                    Contrarian Alerts
                  </h3>
                  <p className="text-zinc-400 text-sm mb-3">
                    When crowd positioning hits extremes and a reversal is
                    imminent. These are the highest-conviction, highest-reward
                    signals we generate.
                  </p>
                  <span className="text-xs font-mono text-zinc-500">
                    Frequency: Ad-hoc · Pro Only
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Pricing ──────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Simple, Transparent{" "}
              <span style={{ color: ACCENT }}>Pricing</span>
            </h2>
            <p className="text-zinc-400">
              Start free. Upgrade when you need the edge.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {/* FREE Tier */}
            <div className="rounded-2xl border border-zinc-800 p-6 sm:p-8 bg-zinc-950/30">
              <div className="mb-6">
                <h3 className="text-xl font-bold mb-1">Free</h3>
                <div className="text-4xl font-bold mb-1">$0</div>
                <p className="text-sm text-zinc-500">Forever free</p>
              </div>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Real-time news feed (130+ sources)</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>3 AI trade setups per day</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Daily morning briefings</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>7-day signal history</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-600">
                  <XIcon />
                  <span>Weekly macro roundups</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-600">
                  <XIcon />
                  <span>6-stage AI trading signals</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-600">
                  <XIcon />
                  <span>Contrarian alerts</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-600">
                  <XIcon />
                  <span>Multi-timeframe analysis</span>
                </li>
              </ul>
              <a
                href="#"
                className="block w-full py-3 rounded-xl text-center font-semibold border border-zinc-700 hover:border-zinc-500 transition-colors"
              >
                Start Free
              </a>
            </div>

            {/* PRO Tier */}
            <div
              className="rounded-2xl border p-6 sm:p-8 relative"
              style={{
                borderColor: ACCENT,
                backgroundColor: `${ACCENT}08`,
              }}
            >
              <div
                className="absolute -top-3 left-6 px-3 py-1 rounded-full text-xs font-bold"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                POPULAR
              </div>
              <div className="mb-6">
                <h3 className="text-xl font-bold mb-1" style={{ color: ACCENT }}>
                  Pro
                </h3>
                <div className="text-4xl font-bold mb-1">$29</div>
                <p className="text-sm text-zinc-500">per month</p>
              </div>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Everything in Free</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Unlimited AI trade setups</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Weekly macro roundups</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Contrarian alerts</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Full 6-stage AI trading signals</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Multi-timeframe analysis</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>COT report analysis</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Economic calendar</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Market regime dashboard</span>
                </li>
                <li className="flex items-center gap-3 text-sm text-zinc-300">
                  <CheckIcon />
                  <span>Unlimited signal history</span>
                </li>
              </ul>
              <a
                href="#"
                className="block w-full py-3 rounded-xl text-center font-semibold transition-all hover:opacity-90"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                Upgrade to Pro
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA Footer ───────────────────────────────────────────────────── */}
      <section className="py-20 px-4 border-t border-zinc-800/60">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Ready to Trade{" "}
            <span style={{ color: ACCENT }}>Smarter</span>?
          </h2>
          <p className="text-zinc-400 mb-10 max-w-xl mx-auto">
            Join thousands of traders using AI-powered intelligence to make
            better decisions. No credit card required for the free tier.
          </p>

          {!submitted ? (
            <form
              onSubmit={handleStartFree}
              className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto"
            >
              <input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="flex-1 px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800 text-white placeholder:text-zinc-500 focus:outline-none focus:border-zinc-600 transition-colors"
              />
              <button
                type="submit"
                className="px-6 py-3 rounded-xl font-semibold transition-all hover:opacity-90 whitespace-nowrap"
                style={{ backgroundColor: ACCENT, color: BG }}
              >
                Get Started Free
              </button>
            </form>
          ) : (
            <div
              className="p-4 rounded-xl border"
              style={{
                borderColor: ACCENT,
                backgroundColor: `${ACCENT}10`,
              }}
            >
              <p className="font-mono text-sm" style={{ color: ACCENT }}>
                {"// Thanks! Check your email to get started."}
              </p>
            </div>
          )}

          <p className="text-xs text-zinc-600 mt-4">
            By signing up, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </section>

      {/* ─── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-zinc-800/60 py-8 px-4">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-500">
              © 2026 SignaLayer.ai — AI Trading Intelligence
            </span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href="#"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Privacy
            </a>
            <a
              href="#"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Terms
            </a>
            <a
              href="#"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

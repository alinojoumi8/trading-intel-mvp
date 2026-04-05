"use client";

import { Suspense } from "react";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { getApiBaseUrl } from "@/lib/config";

const API_BASE = getApiBaseUrl();

interface SubscriptionStatus {
  subscription_tier: string;
  stripe_customer_id: string | null;
  is_pro: boolean;
}

function PricingContent() {
  const { data: session, status } = useSession();
  const searchParams = useSearchParams();
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const upgradeStatus = searchParams.get("upgrade");

  useEffect(() => {
    if (session) {
      fetchSubscriptionStatus();
    }
  }, [session]);

  const fetchSubscriptionStatus = async () => {
    try {
      const token = session?.user?.accessToken;
      if (!token) return;

      const res = await fetch(`${API_BASE}/billing/status`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        setSubscriptionStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch subscription status:", err);
    }
  };

  const handleUpgrade = async () => {
    setLoading(true);
    setError("");

    try {
      const token = session?.user?.accessToken;
      if (!token) throw new Error("Not authenticated");

      const res = await fetch(`${API_BASE}/billing/create-checkout-session`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create checkout session");
      }

      const { checkout_url } = await res.json();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    setLoading(true);
    setError("");

    try {
      const token = session?.user?.accessToken;
      if (!token) throw new Error("Not authenticated");

      const res = await fetch(`${API_BASE}/billing/create-portal-session`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create portal session");
      }

      const { portal_url } = await res.json();
      window.location.href = portal_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  };

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950">
        <div className="text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950 px-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Sign in required</h1>
          <p className="text-zinc-400 mb-6">Please sign in to view pricing plans</p>
          <a
            href="/auth/login"
            className="inline-block bg-zinc-100 hover:bg-white text-zinc-900 font-semibold rounded-lg px-6 py-3 transition-colors"
          >
            Sign in
          </a>
        </div>
      </div>
    );
  }

  const isPro = subscriptionStatus?.is_pro ?? false;

  return (
    <div className="min-h-screen bg-zinc-950 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">Pricing Plans</h1>
          <p className="text-zinc-400 text-lg">
            Choose the plan that fits your trading style
          </p>
        </div>

        {upgradeStatus === "success" && (
          <div className="max-w-md mx-auto mb-8 bg-green-900/30 border border-green-800 text-green-400 rounded-lg px-4 py-3 text-sm text-center">
            Upgrade successful! Welcome to PRO.
          </div>
        )}

        {upgradeStatus === "cancelled" && (
          <div className="max-w-md mx-auto mb-8 bg-yellow-900/30 border border-yellow-800 text-yellow-400 rounded-lg px-4 py-3 text-sm text-center">
            Upgrade cancelled. You can try again anytime.
          </div>
        )}

        {error && (
          <div className="max-w-md mx-auto mb-8 bg-red-900/30 border border-red-800 text-red-400 rounded-lg px-4 py-3 text-sm text-center">
            {error}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {/* Free Tier */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">
            <h2 className="text-xl font-bold text-white mb-2">Free</h2>
            <p className="text-zinc-400 mb-6">Essential market intelligence</p>
            <div className="mb-6">
              <span className="text-4xl font-bold text-white">$0</span>
              <span className="text-zinc-400 ml-2">/month</span>
            </div>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Daily market briefings
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Basic trade setups
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                News aggregation
              </li>
              <li className="flex items-center text-zinc-500">
                <svg className="w-5 h-5 text-zinc-600 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Advanced signals
              </li>
              <li className="flex items-center text-zinc-500">
                <svg className="w-5 h-5 text-zinc-600 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Priority support
              </li>
            </ul>
            <div className="text-center text-zinc-500 text-sm">
              {isPro ? "Current plan" : "You're on this plan"}
            </div>
          </div>

          {/* PRO Tier */}
          <div className="bg-zinc-900 border border-amber-600 rounded-xl p-8 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-600 text-zinc-900 text-xs font-bold px-3 py-1 rounded-full">
              PRO
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Pro</h2>
            <p className="text-zinc-400 mb-6">Full trading intelligence</p>
            <div className="mb-6">
              <span className="text-4xl font-bold text-white">$29</span>
              <span className="text-zinc-400 ml-2">/month</span>
            </div>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Everything in Free
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Advanced AI trading signals
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Multi-timeframe analysis
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                COT data analysis
              </li>
              <li className="flex items-center text-zinc-300">
                <svg className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Priority support
              </li>
            </ul>
            {isPro ? (
              <button
                onClick={handleManageSubscription}
                disabled={loading}
                className="w-full bg-amber-600 hover:bg-amber-500 text-zinc-900 font-semibold rounded-lg px-4 py-3 transition-colors disabled:opacity-50"
              >
                {loading ? "Loading..." : "Manage Subscription"}
              </button>
            ) : (
              <button
                onClick={handleUpgrade}
                disabled={loading}
                className="w-full bg-amber-600 hover:bg-amber-500 text-zinc-900 font-semibold rounded-lg px-4 py-3 transition-colors disabled:opacity-50"
              >
                {loading ? "Loading..." : "Upgrade to PRO"}
              </button>
            )}
          </div>
        </div>

        {isPro && (
          <div className="mt-8 text-center text-green-400 text-sm">
            You&apos;re subscribed to PRO. Thank you for your support!
          </div>
        )}
      </div>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen bg-zinc-950">
        <div className="text-zinc-400">Loading...</div>
      </div>
    }>
      <PricingContent />
    </Suspense>
  );
}

import { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || "https://trading-intel.example.com";

const INSTRUMENTS = [
  "EURUSD",
  "GBPUSD",
  "USDJPY",
  "AUDUSD",
  "XAUUSD",
  "XTIUSD",
  "BTCUSD",
  "ETHUSD",
  "SPXUSD",
  "NASUSD",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const routes: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1.0,
    },
  ];

  // Add instrument pages
  for (const symbol of INSTRUMENTS) {
    routes.push({
      url: `${BASE_URL}/instrument/${symbol}`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.8,
    });
  }

  return routes;
}

import { apiUrl } from "@/lib/api";

export type MarketQuote = {
  ticker: string;
  price_q4: number;
  asof: string;
  source: "manual" | "yahoo";
  fetched_at: number;
  stale: boolean;
  status: "live" | "stale" | "unavailable";
  badge: string;
  provider: string;
};

export async function fetchQuote(ticker: string): Promise<MarketQuote> {
  const response = await fetch(apiUrl(`/api/investments/quotes/${encodeURIComponent(ticker)}`), {
    method: "GET",
    credentials: "include",
    headers: {
      "X-Requested-With": "investflow",
    },
    cache: "no-store",
  });
  if (!response || !response.ok) {
    throw new Error(`quote request failed: ${response?.status ?? 0}`);
  }
  return response.json();
}

export async function setManualQuote(input: {
  ticker: string;
  price_q4: number;
  asof?: string;
}): Promise<MarketQuote> {
  const response = await fetch(apiUrl("/api/investments/quotes/manual"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "investflow",
    },
    body: JSON.stringify(input),
  });
  if (!response || !response.ok) {
    throw new Error(`manual quote update failed: ${response?.status ?? 0}`);
  }
  return response.json();
}

export async function fetchSelectedProvider(): Promise<{ provider: string; disclaimer: string }> {
  const response = await fetch(apiUrl("/api/investments/quote?ticker=AAPL"), {
    method: "GET",
    credentials: "include",
    headers: {
      "X-Requested-With": "investflow",
    },
    cache: "no-store",
  });
  if (!response || !response.ok) {
    return { provider: "yahoo", disclaimer: "Market data provided by Yahoo Finance (unofficial, no SLA)." };
  }
  const quote = (await response.json()) as MarketQuote;
  return {
    provider: quote.provider ?? "yahoo",
    disclaimer: "Yahoo Finance data is unofficial and comes with no SLA; manual entry remains available as a fallback.",
  };
}

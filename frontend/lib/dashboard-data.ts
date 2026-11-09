import { apiUrl } from "@/lib/api";

export type DashboardCardPayload = {
  title: string;
  value_cents?: number;
  delta_pct?: number;
  inflow_cents?: number;
  outflow_cents?: number;
  items?: Array<Record<string, unknown>>;
  href?: string;
};

export type DashboardPayload = {
  dashboard: {
    empty: boolean;
    empty_state?: {
      enabled?: boolean;
      title?: string;
      message?: string;
    };
    cards: Record<string, DashboardCardPayload>;
  };
};

export async function fetchDashboard(): Promise<DashboardPayload> {
  const response = await fetch(apiUrl("/api/dashboard"), {
    method: "GET",
    credentials: "include",
    headers: {
      "X-Requested-With": "investflow",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`dashboard request failed: ${response.status}`);
  }

  return response.json();
}

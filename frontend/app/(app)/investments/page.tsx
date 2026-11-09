"use client";

import { useEffect, useMemo, useState } from "react";

import { apiUrl } from "@/lib/api";
import { fetchQuote } from "@/lib/market-data";

type PositionRow = {
  id: number;
  account_id: number;
  account_name: string | null;
  ticker: string;
  quantity_q4: number;
  avg_cost_q4: number;
  status: "open" | "closed";
  market_value_cents: number;
  realized_gain_loss_cents: number;
  last_price_q4: number;
  last_trade_date: string;
};

type AccountGroup = {
  account_id: number;
  account_name: string;
  total_market_value_cents: number;
  positions: PositionRow[];
};

type InvestmentAccount = {
  id: number;
  name: string;
  code?: string;
  subtype?: string;
  is_investment?: boolean;
  is_archived?: boolean;
};

const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const quantityFromQ4 = (q4: number) => (q4 / 10_000).toFixed(4);
const toQ4 = (value: number) => Math.max(0, Math.round(Number(value) * 10_000));

export default function InvestmentsPage() {
  const [groups, setGroups] = useState<AccountGroup[]>([]);
  const [accounts, setAccounts] = useState<InvestmentAccount[]>([]);
  const [overallTotal, setOverallTotal] = useState(0);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [quoteBadge, setQuoteBadge] = useState<string>("Market data unavailable");

  async function load() {
    const response = await fetch(apiUrl("/api/investments/positions"), {
      credentials: "include",
      headers: { "X-Requested-With": "investflow" },
    });
    if (!response || !response.ok) {
      setError("Unable to load positions right now.");
      return;
    }
    const payload = (await response.json()) as {
      account_groups: AccountGroup[];
      overall_total_market_value_cents: number;
    };
    setGroups(payload.account_groups ?? []);
    setOverallTotal(payload.overall_total_market_value_cents ?? 0);
  }

  async function loadAccounts() {
    const response = await fetch(apiUrl("/api/investments/accounts"), {
      credentials: "include",
      headers: { "X-Requested-With": "investflow" },
    });
    if (!response || !response.ok) {
      return;
    }
    const payload = (await response.json()) as { accounts?: InvestmentAccount[] };
    setAccounts(payload.accounts ?? []);
  }

  useEffect(() => {
    void loadAccounts().catch(() => undefined);
    void load().catch(() => undefined);

    const symbol = groups[0]?.positions[0]?.ticker;
    if (!symbol) {
      return;
    }

    void fetchQuote(symbol)
      .then((quote) => setQuoteBadge(quote.badge ?? "Market data unavailable"))
      .catch(() => setQuoteBadge("Yahoo Finance unavailable; manual fallback available"));
  }, [groups]);

  const totalLabel = useMemo(() => money(overallTotal), [overallTotal]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setIsBusy(true);

    const form = new FormData(event.currentTarget);
    const quantity = Number(form.get("quantity_q4") ?? 0);
    const price = Number(form.get("price_q4") ?? 0);
    const payload = {
      account_id: Number(form.get("account_id")),
      ticker: String(form.get("ticker") ?? "").trim().toUpperCase(),
      side: String(form.get("side") ?? "buy"),
      quantity_q4: toQ4(quantity),
      price_q4: toQ4(price),
      fee_cents: Number(form.get("fee_cents") ?? 0),
      trade_date: String(form.get("trade_date") ?? new Date().toISOString().slice(0, 10)),
    };

    const response = await fetch(apiUrl("/api/investments/trades"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const payloadJson = (await response.json().catch(() => ({}))) as { detail?: string };
      setError(payloadJson.detail ?? "Trade failed");
      setIsBusy(false);
      return;
    }
    setMessage("Position updated.");
    setIsBusy(false);
    event.currentTarget.reset();
    await load();
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Investments</h1>
      <p className="mt-2 text-sm opacity-70">Manual brokerage positions with average-cost tracking.</p>

      <div className="mt-6 card bg-base-200 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm uppercase tracking-wide opacity-70">Total market value</div>
            <div className="text-3xl font-bold">{totalLabel}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-base-300 bg-base-100 px-4 py-3 text-sm">
        <div className="font-medium">Quote status</div>
        <div className="mt-1 opacity-80">{quoteBadge}</div>
        <div className="mt-2 text-xs opacity-70">
          Yahoo Finance data is unofficial and has no SLA; manual fallback remains available for prices.
        </div>
      </div>

      {message ? <p className="mt-4 text-success">{message}</p> : null}
      {error ? <p className="mt-4 text-error">{error}</p> : null}

      <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="card bg-base-100 p-4 shadow-sm">
          <h2 className="text-xl font-semibold">Positions by account</h2>
          <div className="mt-4 space-y-4">
            {groups.length === 0 ? (
              <p className="text-sm opacity-70">No open positions yet.</p>
            ) : (
              groups.map((group) => (
                <div key={group.account_id} className="rounded-xl border border-base-300 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="font-semibold">{group.account_name}</h3>
                    <span className="text-sm font-medium">{money(group.total_market_value_cents)}</span>
                  </div>
                  <div className="space-y-2">
                    {group.positions.map((position) => (
                      <div key={position.id} className="flex items-center justify-between rounded-lg bg-base-200 px-3 py-2 text-sm">
                        <div>
                          <div className="font-medium">{position.ticker}</div>
                          <div className="opacity-70">{quantityFromQ4(position.quantity_q4)} shares</div>
                        </div>
                        <div className="text-right">
                          <div>{money(position.market_value_cents)}</div>
                          <div className="opacity-70">avg {money(position.avg_cost_q4 / 100)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <form className="card bg-base-100 p-4 shadow-sm" onSubmit={onSubmit}>
          <h2 className="text-xl font-semibold">Manual trade</h2>
          <div className="mt-4 grid gap-3">
            <label className="form-control">
              <span className="label-text">Account</span>
              <select name="account_id" className="select select-bordered min-h-11" defaultValue="" required>
                <option value="" disabled>
                  {accounts.length > 0 ? "Select a brokerage account" : "Loading accounts..."}
                </option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-control">
              <span className="label-text">Ticker</span>
              <input name="ticker" className="input input-bordered min-h-11" placeholder="AAPL" required />
            </label>
            <label className="form-control">
              <span className="label-text">Side</span>
              <select name="side" className="select select-bordered min-h-11" defaultValue="buy">
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </label>
            <label className="form-control">
              <span className="label-text">Quantity</span>
              <input name="quantity_q4" className="input input-bordered min-h-11" type="number" step="0.0001" defaultValue={2} required />
            </label>
            <label className="form-control">
              <span className="label-text">Price</span>
              <input name="price_q4" className="input input-bordered min-h-11" type="number" step="0.0001" defaultValue={150.5} required />
            </label>
            <label className="form-control">
              <span className="label-text">Fee (cents)</span>
              <input name="fee_cents" className="input input-bordered min-h-11" type="number" defaultValue={0} />
            </label>
            <label className="form-control">
              <span className="label-text">Trade date</span>
              <input name="trade_date" className="input input-bordered min-h-11" type="date" defaultValue={new Date().toISOString().slice(0, 10)} />
            </label>
            <button type="submit" className="btn btn-primary min-h-11" disabled={isBusy}>
              {isBusy ? "Posting…" : "Post trade"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

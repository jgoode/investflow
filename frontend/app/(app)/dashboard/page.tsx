"use client";

import { useEffect, useState, type ReactNode } from "react";

import { fetchDashboard, type DashboardPayload } from "@/lib/dashboard-data";

function formatMoney(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

function getDefaultHref(cardKey: string) {
  switch (cardKey) {
    case "net_worth":
      return "/reports/net_worth";
    case "cash_flow":
      return "/reports/cash_flow";
    case "income_expense":
      return "/reports/monthly";
    case "holdings":
      return "/reports/net_worth";
    case "accounts_summary":
      return "/accounts";
    case "recent_transactions":
      return "/transactions";
    default:
      return "/dashboard";
  }
}

function getUnderlyingHref(cardKey: string, href?: string) {
  return href ?? getDefaultHref(cardKey);
}

function getCsvContent(cardKey: string, card: Record<string, unknown>) {
  switch (cardKey) {
    case "net_worth":
      return `net_worth,value_cents,${Number(card.value_cents ?? 0)}`;
    case "cash_flow":
      return `cash_flow,inflow_cents,outflow_cents,${Number(card.inflow_cents ?? 0)},${Number(card.outflow_cents ?? 0)}`;
    case "income_expense": {
      const rows = Array.isArray(card.items) ? card.items : [];
      return [
        "period,income_cents,expense_cents",
        ...rows.map((row) => {
          const item = row as Record<string, unknown>;
          return `${String(item.period ?? "")},${Number(item.income_cents ?? 0)},${Number(item.expense_cents ?? 0)}`;
        }),
      ].join("\n");
    }
    case "holdings":
      return `portfolio_holdings,value_cents,${Number(card.value_cents ?? 0)}`;
    case "accounts_summary": {
      const rows = Array.isArray(card.items) ? card.items : [];
      return [
        "type,balance_cents",
        ...rows.map((row) => {
          const item = row as Record<string, unknown>;
          return `${String(item.type ?? "")},${Number(item.balance_cents ?? 0)}`;
        }),
      ].join("\n");
    }
    case "recent_transactions": {
      const rows = Array.isArray(card.items) ? card.items : [];
      return [
        "date,description,amount_cents",
        ...rows.map((row) => {
          const item = row as Record<string, unknown>;
          return `${String(item.date ?? "")},${String(item.description ?? "")},${Number(item.amount_cents ?? 0)}`;
        }),
      ].join("\n");
    }
    default:
      return "";
  }
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  useEffect(() => {
    void fetchDashboard()
      .then((payload) => setData(payload))
      .catch(() => {
        setData({
          dashboard: {
            empty: true,
            cards: {},
            empty_state: {
              enabled: true,
              title: "Start your book",
              message: "No data yet. Add accounts and transactions to populate the dashboard.",
            },
          },
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const dashboard = data?.dashboard;
  const cards = dashboard?.cards ?? {};

  const openLocation = (href: string) => {
    if (typeof window !== "undefined") {
      window.location.assign(href);
    }
  };

  const renderCard = (cardKey: string, card: Record<string, unknown>, children: ReactNode) => {
    const cardHref = getUnderlyingHref(cardKey, typeof card.href === "string" ? card.href : undefined);
    const menuItems = [
      { label: "Open report", href: cardHref },
      { label: "Open underlying", href: cardHref },
      {
        label: "Copy CSV",
        onSelect: async () => {
          const content = getCsvContent(cardKey, card);
          if (content && typeof navigator !== "undefined" && navigator.clipboard) {
            await navigator.clipboard.writeText(content);
          }
        },
      },
    ];

    return (
      <section
        key={cardKey}
        data-testid={cardKey === "net_worth" ? "net-worth-card" : `${cardKey}-card`}
        className="card relative border border-base-300 bg-base-100 shadow-sm"
        onContextMenu={(event) => {
          event.preventDefault();
          setOpenMenu(cardKey);
        }}
        onDoubleClick={() => openLocation(cardHref)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openLocation(cardHref);
          }
        }}
        tabIndex={0}
      >
        {openMenu === cardKey ? (
          <div role="menu" className="absolute right-3 top-3 z-10 rounded border border-base-300 bg-base-100 p-2 shadow-lg">
            {menuItems.map((item) => (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-base-200"
                onClick={() => {
                  if (item.href) {
                    openLocation(item.href);
                  } else if (item.onSelect) {
                    void item.onSelect();
                  }
                  setOpenMenu(null);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
        {children}
      </section>
    );
  };

  return (
    <main className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold">Dashboard</h1>
        <div className="text-sm opacity-70">{dashboard?.empty ? "Onboarding" : "Live"}</div>
      </div>

      {dashboard?.empty_state?.enabled ? (
        <div className="mb-6 grid gap-4 md:grid-cols-3">
          <div className="card border border-base-300 bg-base-100 shadow-sm">
            <div className="card-body">
              <h2 className="card-title text-base">{dashboard.empty_state.title}</h2>
              <p>{dashboard.empty_state.message}</p>
            </div>
          </div>
          <div className="card border border-base-300 bg-base-100 shadow-sm">
            <div className="card-body">
              <h2 className="card-title text-base">Accounts</h2>
              <p>Add the starter chart of accounts to begin tracking balances.</p>
            </div>
          </div>
          <div className="card border border-base-300 bg-base-100 shadow-sm">
            <div className="card-body">
              <h2 className="card-title text-base">Transactions</h2>
              <p>Post your first income or expense to surface the cash-flow dashboard.</p>
            </div>
          </div>
        </div>
      ) : null}

      {loading ? <div className="opacity-70">Loading dashboard…</div> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.net_worth
          ? renderCard("net_worth", cards.net_worth as Record<string, unknown>, (
              <div className="card-body">
                <div className="flex items-center justify-between">
                  <h2 className="card-title text-base">Net worth</h2>
                  <a href={cards.net_worth.href ?? "/reports/net_worth"} className="link link-primary text-xs">
                    View report
                  </a>
                </div>
                <div className="mt-2 text-2xl font-semibold">{formatMoney(cards.net_worth.value_cents ?? 0)}</div>
                <div className="text-sm opacity-75">
                  {cards.net_worth.delta_pct !== undefined
                    ? `${cards.net_worth.delta_pct > 0 ? "+" : ""}${cards.net_worth.delta_pct}% over trailing window`
                    : "No trend data"}
                </div>
              </div>
            ))
          : null}

        {cards.cash_flow
          ? renderCard("cash_flow", cards.cash_flow as Record<string, unknown>, (
              <div className="card-body">
                <div className="flex items-center justify-between">
                  <h2 className="card-title text-base">Cash flow</h2>
                  <a href={cards.cash_flow.href ?? "/reports/cash_flow"} className="link link-primary text-xs">
                    View report
                  </a>
                </div>
                <div className="mt-2 text-lg font-medium">In {formatMoney(cards.cash_flow.inflow_cents ?? 0)}</div>
                <div className="text-sm opacity-75">Out {formatMoney(cards.cash_flow.outflow_cents ?? 0)}</div>
              </div>
            ))
          : null}

        {cards.income_expense
          ? renderCard("income_expense", cards.income_expense as Record<string, unknown>, (
              <div className="card-body">
                <div className="flex items-center justify-between">
                  <h2 className="card-title text-base">Income / expense</h2>
                  <a href={cards.income_expense.href ?? "/reports/monthly"} className="link link-primary text-xs">
                    View report
                  </a>
                </div>
                <div className="mt-3 space-y-2">
                  {(cards.income_expense.items ?? []).slice(-6).map((row) => {
                    const item = row as Record<string, unknown>;
                    const income = Number(item.income_cents ?? 0);
                    const expense = Number(item.expense_cents ?? 0);
                    return (
                      <div key={String(item.period ?? "unknown")} className="space-y-1">
                        <div className="flex items-center justify-between text-xs opacity-70">
                          <span>{String(item.period ?? "")}</span>
                          <span>{formatMoney(income - expense)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-base-200">
                          <div
                            className="h-full rounded-full bg-success"
                            style={{ width: `${Math.min((income / Math.max(income + expense, 1)) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          : null}

        {cards.holdings
          ? renderCard("holdings", cards.holdings as Record<string, unknown>, (
              <div className="card-body">
                <div className="flex items-center justify-between">
                  <h2 className="card-title text-base">Portfolio holdings</h2>
                  <a href={cards.holdings.href ?? "/reports/net_worth"} className="link link-primary text-xs">
                    View report
                  </a>
                </div>
                <div className="mt-2 text-2xl font-semibold">{formatMoney(cards.holdings.value_cents ?? 0)}</div>
              </div>
            ))
          : null}

        {cards.accounts_summary
          ? renderCard("accounts_summary", cards.accounts_summary as Record<string, unknown>, (
              <div className="card-body">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="card-title text-base">Accounts</h2>
                  <a href={cards.accounts_summary.href ?? "/accounts"} className="link link-primary text-xs">
                    View all
                  </a>
                </div>
                <div className="space-y-2">
                  {(cards.accounts_summary.items ?? []).map((item) => {
                    const summary = item as Record<string, unknown>;
                    return (
                      <div key={String(summary.type ?? "account")} className="flex items-center justify-between">
                        <span className="capitalize">{String(summary.type ?? "")}</span>
                        <span>{formatMoney(Number(summary.balance_cents ?? 0))}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          : null}

        {cards.recent_transactions
          ? renderCard("recent_transactions", cards.recent_transactions as Record<string, unknown>, (
              <div className="card-body">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="card-title text-base">Recent activity</h2>
                  <a href={cards.recent_transactions.href ?? "/transactions"} className="link link-primary text-xs">
                    View all
                  </a>
                </div>
                <div className="space-y-2">
                  {(cards.recent_transactions.items ?? []).map((item) => {
                    const tx = item as Record<string, unknown>;
                    const isIncome = Number(tx.amount_cents ?? 0) >= 0;
                    return (
                      <div
                        key={String(tx.id ?? "tx")}
                        className="flex items-center justify-between gap-3 rounded-sm border border-base-200 px-2 py-1.5"
                      >
                        <div>
                          <div className="font-medium">{String(tx.description ?? "Transaction")}</div>
                          <div className="text-xs opacity-70">{String(tx.date ?? "—")}</div>
                        </div>
                        <div className={isIncome ? "text-success" : "text-error"}>
                          {formatMoney(Number(tx.amount_cents ?? 0))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          : null}
      </div>
    </main>
  );
}

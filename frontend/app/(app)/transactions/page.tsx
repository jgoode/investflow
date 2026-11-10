"use client";

import { useEffect, useMemo, useState } from "react";

import { apiUrl } from "@/lib/api";

type AccountRow = {
  id: number;
  code: string;
  name: string;
  type: string;
  is_archived: boolean;
};

type CategoryRow = {
  id: number;
  name: string;
  flow: "income" | "expense";
  default_account_id: number | null;
};

type TransactionLine = {
  id: number;
  account_id: number;
  account_name: string;
  account_type: string;
  account_number_mask: string;
  direction: "debit" | "credit";
  amount_cents: number;
  memo: string | null;
  category_id: number | null;
  category_name: string | null;
};

type TransactionRow = {
  id: number;
  date: string;
  description: string;
  reference: string | null;
  status: string;
  lines: TransactionLine[];
};

const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export default function TransactionsPage() {
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const getLocalDateIso = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const [draft, setDraft] = useState({
    date: getLocalDateIso(),
    description: "",
    amountCents: "",
    mode: "expense" as "income" | "expense",
    accountId: "",
    categoryId: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const accountChoices = useMemo(
    () => accounts.filter((row) => !row.is_archived && row.type !== "equity").sort((a, b) => a.name.localeCompare(b.name)),
    [accounts],
  );

  const categoryChoices = useMemo(
    () =>
      categories
        .filter((row) => row.flow === draft.mode)
        .sort((a, b) => a.name.localeCompare(b.name)),
    [categories, draft.mode],
  );

  async function load() {
    const [accountsResp, categoriesResp, txResp] = await Promise.all([
      fetch(apiUrl("/api/accounts"), {
        credentials: "include",
        headers: { "X-Requested-With": "investflow" },
      }),
      fetch(apiUrl("/api/categories"), {
        credentials: "include",
        headers: { "X-Requested-With": "investflow" },
      }),
      fetch(apiUrl("/api/transactions?limit=20&page=1"), {
        credentials: "include",
        headers: { "X-Requested-With": "investflow" },
      }),
    ]);

    if (accountsResp.ok) {
      const payload = (await accountsResp.json()) as { accounts: AccountRow[] };
      setAccounts(payload.accounts);
    }
    if (categoriesResp.ok) {
      const payload = (await categoriesResp.json()) as { categories: CategoryRow[] };
      setCategories(payload.categories);
    }
    if (txResp.ok) {
      const payload = (await txResp.json()) as { transactions: TransactionRow[] };
      setTransactions(payload.transactions ?? []);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const amount = Number(draft.amountCents);
    const payload = {
      date: draft.date,
      description: draft.description.trim(),
      mode: draft.mode,
      account_id: Number(draft.accountId),
      category_id: Number(draft.categoryId),
      amount_cents: Number.isFinite(amount) ? Math.round(amount) : 0,
    };

    const response = await fetch(apiUrl("/api/transactions"), {
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
      setError(payloadJson.detail ?? "Transaction failed");
      return;
    }

    setMessage("Transaction posted.");
    setDraft({
      date: getLocalDateIso(),
      description: "",
      amountCents: "",
      mode: "expense",
      accountId: "",
      categoryId: "",
    });
    await load();
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Transactions</h1>
      <p className="mt-2 text-sm opacity-70">Quick expense and income entries with balance enforcement.</p>
      {message ? <p className="mt-4 text-success">{message}</p> : null}
      {error ? <p className="mt-4 text-error">{error}</p> : null}

      <form className="mt-6 grid gap-3 md:grid-cols-2" onSubmit={onSubmit}>
        <label className="form-control">
          <span className="label-text">Date</span>
          <input
            type="date"
            className="input input-bordered min-h-11"
            value={draft.date}
            onChange={(event) => setDraft((prev) => ({ ...prev, date: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Mode</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.mode}
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, mode: event.target.value as "income" | "expense" }))
            }
          >
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </label>
        <label className="form-control md:col-span-2">
          <span className="label-text">Description</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.description}
            onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Posting account</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.accountId}
            onChange={(event) => setDraft((prev) => ({ ...prev, accountId: event.target.value }))}
          >
            <option value="">Select account</option>
            {accountChoices.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label className="form-control">
          <span className="label-text">Category</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.categoryId}
            onChange={(event) => setDraft((prev) => ({ ...prev, categoryId: event.target.value }))}
          >
            <option value="">Select category</option>
            {categoryChoices.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label className="form-control md:col-span-2">
          <span className="label-text">Amount (cents)</span>
          <input
            inputMode="numeric"
            className="input input-bordered min-h-11"
            value={draft.amountCents}
            onChange={(event) => setDraft((prev) => ({ ...prev, amountCents: event.target.value }))}
          />
        </label>
        <div className="md:col-span-2">
          <button type="submit" className="btn btn-primary min-h-11">
            Post transaction
          </button>
        </div>
      </form>

      <div className="mt-10 overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Lines</th>
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-4 text-center opacity-70">
                  No transactions in the current range.
                </td>
              </tr>
            ) : (
              transactions.map((row) => (
                <tr key={row.id}>
                  <td>{row.date}</td>
                  <td>{row.description}</td>
                  <td>
                    <ul className="space-y-1 text-sm">
                      {row.lines.map((line) => (
                        <li key={line.id}>
                          {line.direction} {money(line.amount_cents)} · {line.account_name} ({line.account_number_mask})
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

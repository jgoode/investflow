"use client";

import { useEffect, useState } from "react";

import { apiUrl } from "@/lib/api";

type AccountRow = {
  id: number;
  code: string;
  name: string;
  type: string;
  subtype: string;
  parent_id: number | null;
  institution: string | null;
  description: string | null;
  is_archived: boolean;
  is_investment: boolean;
  last4: string | null;
};

export default function AccountsPage() {
  const [rows, setRows] = useState<AccountRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    code: "CHK-01",
    name: "Checking",
    type: "asset",
    subtype: "bank",
    institution: "Demo Bank",
    description: "Primary checking account",
  });

  async function loadAccounts() {
    const response = await fetch(apiUrl("/api/accounts"), {
      credentials: "include",
      headers: { "X-Requested-With": "investflow" },
    });
    if (!response.ok) {
      setError("Unable to load accounts.");
      return;
    }
    const payload = (await response.json()) as { accounts: AccountRow[] };
    setRows(payload.accounts);
  }

  useEffect(() => {
    void loadAccounts();
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);

    const response = await fetch(apiUrl("/api/accounts"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({
        ...draft,
        parent_id: null,
        is_investment: false,
      }),
    });

    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setError(payload.detail ?? "Create account failed");
      return;
    }

    setMessage("Account created.");
    setDraft({
      code: "",
      name: "",
      type: "asset",
      subtype: "cash",
      institution: "",
      description: "",
    });
    await loadAccounts();
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Chart of accounts</h1>
      <p className="mt-2 text-sm opacity-70">Editable seeded COA for the shared book.</p>

      {message ? <p className="mt-4 text-success">{message}</p> : null}
      {error ? <p className="mt-4 text-error">{error}</p> : null}

      <form className="mt-6 grid gap-3 md:grid-cols-2" onSubmit={submit}>
        <label className="form-control">
          <span className="label-text">Code</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.code}
            onChange={(event) => setDraft((prev) => ({ ...prev, code: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Name</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Type</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.type}
            onChange={(event) => setDraft((prev) => ({ ...prev, type: event.target.value }))}
          >
            <option value="asset">Asset</option>
            <option value="liability">Liability</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
            <option value="equity">Equity</option>
          </select>
        </label>
        <label className="form-control">
          <span className="label-text">Subtype</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.subtype}
            onChange={(event) => setDraft((prev) => ({ ...prev, subtype: event.target.value }))}
          >
            <option value="cash">Cash</option>
            <option value="bank">Bank</option>
            <option value="brokerage">Brokerage</option>
            <option value="credit_card">Credit card</option>
            <option value="fund">Fund</option>
            <option value="group">Group</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label className="form-control md:col-span-2">
          <span className="label-text">Institution</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.institution}
            onChange={(event) => setDraft((prev) => ({ ...prev, institution: event.target.value }))}
          />
        </label>
        <label className="form-control md:col-span-2">
          <span className="label-text">Description</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.description}
            onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
          />
        </label>
        <div className="md:col-span-2">
          <button type="submit" className="btn btn-primary min-h-11">
            Add account
          </button>
        </div>
      </form>

      <div className="mt-8 overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>Subtype</th>
              <th>Archived</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.code}</td>
                <td>{row.name}</td>
                <td>{row.type}</td>
                <td>{row.subtype}</td>
                <td>{row.is_archived ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

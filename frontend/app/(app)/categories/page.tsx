"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiUrl } from "@/lib/api";

type CategoryRow = {
  id: number;
  name: string;
  flow: "income" | "expense";
  color: string;
  default_account_id: number | null;
};

type AccountRow = {
  id: number;
  code: string;
  name: string;
  type: string;
  is_archived: boolean;
};

export default function CategoriesPage() {
  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [draft, setDraft] = useState({
    name: "",
    flow: "expense" as "income" | "expense",
    color: "#64748b",
    defaultAccountId: "",
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const accountOptions = useMemo(
    () =>
      accounts
        .filter((row) => !row.is_archived && (row.type === draft.flow || row.type === ""))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [accounts, draft.flow],
  );

  const load = useCallback(async () => {
    const [categoriesResp, accountsResp] = await Promise.all([
      fetch(apiUrl("/api/categories"), {
        credentials: "include",
        headers: { "X-Requested-With": "investflow" },
      }),
      fetch(apiUrl("/api/accounts"), {
        credentials: "include",
        headers: { "X-Requested-With": "investflow" },
      }),
    ]);
    if (!categoriesResp.ok || !accountsResp.ok) {
      setError("Unable to load categories.");
      return;
    }

    const categoriesPayload = (await categoriesResp.json()) as { categories: CategoryRow[] };
    const accountsPayload = (await accountsResp.json()) as { accounts: AccountRow[] };
    setCategories(categoriesPayload.categories);
    setAccounts(accountsPayload.accounts);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createCategory(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);

    const response = await fetch(apiUrl("/api/categories"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({
        name: draft.name,
        flow: draft.flow,
        color: draft.color,
        default_account_id: draft.defaultAccountId ? Number(draft.defaultAccountId) : null,
      }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setError(payload.detail ?? "Create category failed");
      return;
    }

    setMessage("Category created.");
    setDraft({
      name: "",
      flow: "expense",
      color: "#64748b",
      defaultAccountId: "",
    });
    await load();
  }

  async function saveCategory(row: CategoryRow): Promise<void> {
    setMessage(null);
    setError(null);

    const response = await fetch(apiUrl(`/api/categories/${row.id}`), {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({
        name: row.name,
        flow: row.flow,
        color: row.color,
        default_account_id: row.default_account_id,
      }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setError(payload.detail ?? "Save category failed");
      return;
    }

    setMessage("Category updated.");
    await load();
  }

  async function deleteCategory(row: CategoryRow): Promise<void> {
    setMessage(null);
    setError(null);
    const response = await fetch(apiUrl(`/api/categories/${row.id}`), {
      method: "DELETE",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({ confirm: true }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setError(payload.detail ?? "Delete category failed");
      return;
    }
    setMessage("Category deleted.");
    await load();
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Categories</h1>
      <p className="mt-2 text-sm opacity-70">
        Income and expense categories with optional default posting account.
      </p>
      {message ? <p className="mt-4 text-success">{message}</p> : null}
      {error ? <p className="mt-4 text-error">{error}</p> : null}

      <form className="mt-6 grid gap-3 md:grid-cols-2" onSubmit={createCategory}>
        <label className="form-control">
          <span className="label-text">Name</span>
          <input
            aria-label="Name"
            className="input input-bordered min-h-11"
            value={draft.name}
            onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Flow</span>
          <select
            aria-label="Flow"
            className="select select-bordered min-h-11"
            value={draft.flow}
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, flow: event.target.value as "income" | "expense" }))
            }
          >
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </select>
        </label>
        <label className="form-control">
          <span className="label-text">Color</span>
          <input
            className="input input-bordered min-h-11"
            value={draft.color}
            onChange={(event) => setDraft((prev) => ({ ...prev, color: event.target.value }))}
          />
        </label>
        <label className="form-control">
          <span className="label-text">Default account</span>
          <select
            className="select select-bordered min-h-11"
            value={draft.defaultAccountId}
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, defaultAccountId: event.target.value }))
            }
          >
            <option value="">(none)</option>
            {accountOptions.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <div className="md:col-span-2">
          <button type="submit" className="btn btn-primary min-h-11">
            Save category
          </button>
        </div>
      </form>

      <div className="mt-8 overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Flow</th>
              <th>Color</th>
              <th>Default account</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((row) => (
              <tr key={row.id}>
                <td>
                  <input
                    className="input input-bordered input-sm min-h-11 w-full max-w-xs"
                    value={row.name}
                    onChange={(event) =>
                      setCategories((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, name: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td>
                  <select
                    className="select select-bordered select-sm min-h-11"
                    value={row.flow}
                    onChange={(event) =>
                      setCategories((prev) =>
                        prev.map((item) =>
                          item.id === row.id
                            ? { ...item, flow: event.target.value as "income" | "expense" }
                            : item,
                        ),
                      )
                    }
                  >
                    <option value="expense">Expense</option>
                    <option value="income">Income</option>
                  </select>
                </td>
                <td>
                  <input
                    className="input input-bordered input-sm min-h-11"
                    value={row.color}
                    onChange={(event) =>
                      setCategories((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, color: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </td>
                <td>
                  <select
                    className="select select-bordered select-sm min-h-11"
                    value={row.default_account_id ?? ""}
                    onChange={(event) =>
                      setCategories((prev) =>
                        prev.map((item) =>
                          item.id === row.id
                            ? {
                                ...item,
                                default_account_id: event.target.value
                                  ? Number(event.target.value)
                                  : null,
                              }
                            : item,
                        ),
                      )
                    }
                  >
                    <option value="">(none)</option>
                    {accounts
                      .filter(
                        (account) => !account.is_archived && account.type === row.flow,
                      )
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.name}
                        </option>
                      ))}
                  </select>
                </td>
                <td className="flex gap-2">
                  <button
                    type="button"
                    className="btn btn-xs min-h-11"
                    onClick={() => {
                      void saveCategory(row);
                    }}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${row.name}`}
                    className="btn btn-xs btn-error min-h-11"
                    onClick={() => {
                      void deleteCategory(row);
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

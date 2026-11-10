"use client";

import { useEffect, useRef, useState } from "react";

import { apiUrl } from "@/lib/api";

type StarterTemplate = {
  name: string;
  kind: string;
  column_mapping: Record<string, string>;
};

type AccountOption = {
  id: number;
  name: string;
  type: string;
  subtype: string;
};

type PreviewRowError = { row_index: number; errors: string[] };
type PreviewDuplicate = { row_index: number; hash: string };
type WouldPostRow = {
  row_index: number;
  action?: string;
  account?: string;
  ticker?: string;
  quantity_q4?: number;
  avg_cost_q4?: number;
  amount_cents?: number;
  resulting_quantity_q4?: number;
  realized_gain_loss_cents?: number;
};
type PreviewPayload = {
  kind: string;
  total_rows: number;
  valid_rows: number;
  error_rows: PreviewRowError[];
  duplicates: PreviewDuplicate[];
  absent_holdings: Array<{ account_id: number; ticker: string }>;
  would_post: WouldPostRow[];
};

type CommitCounts = { posted: number; duplicate: number; removed: number };

const money = (cents: number | undefined) =>
  cents === undefined ? "" : `$${(cents / 100).toFixed(2)}`;
const quantity = (q4: number | undefined) =>
  q4 === undefined ? "" : (q4 / 10_000).toString();

const KIND_OPTIONS = [
  { value: "positions", label: "Positions snapshot" },
  { value: "trades", label: "Trade history" },
];

export default function ImportPage() {
  const [templates, setTemplates] = useState<StarterTemplate[]>([]);
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [kind, setKind] = useState<"positions" | "trades">("positions");
  const [fileName, setFileName] = useState("");
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [result, setResult] = useState<CommitCounts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await fetch(apiUrl("/api/imports/templates"), {
          credentials: "include",
        });
        if (!response.ok) return;
        const payload = (await response.json()) as {
          templates?: StarterTemplate[];
          accounts?: AccountOption[];
        };
        if (cancelled) return;
        setTemplates(payload.templates ?? []);
        setAccounts(payload.accounts ?? []);
      } catch {
        // wizard still usable; bindings resolve on the backend
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function bindings(): Record<string, number> {
    return Object.fromEntries(accounts.map((account) => [account.name, account.id]));
  }

  function columnMapping(): Record<string, string> | undefined {
    const template = templates.find((entry) => entry.kind === kind);
    return template ? template.column_mapping : undefined;
  }

  function body(extra: Record<string, unknown>) {
    return {
      kind,
      csv_text: csvText,
      file_name: fileName || "portfolio.csv",
      column_mapping: columnMapping(),
      account_bindings: bindings(),
      ...extra,
    };
  }

  async function post(path: string, payload: unknown) {
    return fetch(apiUrl(path), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify(payload),
    });
  }

  async function readError(response: Response, fallback: string) {
    const payload = (await response.json().catch(() => ({}))) as {
      detail?: string | { message?: string };
    };
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") return detail.message;
    return fallback;
  }

  async function runPreview() {
    setIsBusy(true);
    setError(null);
    setPreview(null);
    setResult(null);
    try {
      const response = await post("/api/imports/preview", body({ confirm: false }));
      if (!response.ok) {
        setError(await readError(response, "Preview failed."));
        return;
      }
      setPreview((await response.json()) as PreviewPayload);
    } catch {
      setError("Preview failed: the import service is unreachable.");
    } finally {
      setIsBusy(false);
    }
  }

  async function confirmImport() {
    setIsBusy(true);
    setError(null);
    const absent = preview?.absent_holdings ?? [];
    try {
      const response = await post(
        "/api/imports/commit",
        body({
          confirm: true,
          confirm_absent_removals: absent.length > 0 ? true : undefined,
        }),
      );
      if (!response.ok) {
        setError(await readError(response, "Import failed."));
        return;
      }
      const payload = (await response.json()) as { counts: CommitCounts };
      setResult(payload.counts);
      setPreview(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setCsvText("");
      setFileName("");
    } catch {
      setError("Import failed: the import service is unreachable.");
    } finally {
      setIsBusy(false);
    }
  }

  async function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setPreview(null);
    setResult(null);
    setError(null);
    if (!file) {
      setCsvText("");
      setFileName("");
      return;
    }
    setFileName(file.name);
    setCsvText(await file.text());
  }

  const templateNames = templates
    .filter((template) => template.kind === kind)
    .map((template) => template.name);

  return (
    <main className="mx-auto max-w-4xl space-y-8 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold">Import portfolio data</h1>
        <p className="mt-1 text-sm opacity-70">
          Portfolio CSV import — map your accounts, preview every row, and confirm.
          Nothing is written until you confirm.
        </p>
      </header>

      <section className="rounded-md border border-base-300 bg-base-100 p-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="form-control">
            <span className="label-text">Import kind</span>
            <select
              aria-label="Import kind"
              className="select select-bordered min-h-11"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as "positions" | "trades");
                setPreview(null);
                setResult(null);
              }}
            >
              {KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-control">
            <span className="label-text">CSV file</span>
            <input
              aria-label="CSV file"
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="file-input file-input-bordered min-h-11"
              onChange={onFileChange}
            />
          </label>
        </div>
        {templateNames.length > 0 ? (
          <p className="mt-3 text-xs opacity-60">
            Starter templates for this kind: {templateNames.join(", ")}. Columns are
            auto-detected from the template headers when present.
          </p>
        ) : null}
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            className="btn btn-primary min-h-11"
            onClick={runPreview}
            disabled={isBusy}
          >
            Run preview
          </button>
          <button
            type="button"
            className="btn min-h-11"
            onClick={confirmImport}
            disabled={isBusy || !preview || preview.error_rows.length > 0}
          >
            Confirm import
          </button>
        </div>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-error">
            {error}
          </p>
        ) : null}
        {!csvText ? (
          <p className="mt-3 text-xs opacity-60">
            Select a CSV file to enable the preview. Limits: 5 MB and 5,000 rows per
            file — larger files must be split.
          </p>
        ) : null}
      </section>

      {preview ? (
        <section
          aria-label="Import preview"
          className="rounded-md border border-base-300 bg-base-100 p-4"
        >
          <h2 className="text-lg font-semibold">Import preview</h2>
          <p className="mt-1 text-sm">
            {preview.total_rows} rows · {preview.valid_rows} ready ·{" "}
            {preview.error_rows.length} with errors · {preview.duplicates.length}{" "}
            duplicates
          </p>

          {preview.absent_holdings.length > 0 ? (
            <div className="mt-3 rounded-md border border-warning bg-warning/10 p-3 text-sm">
              <p className="font-medium">Holdings absent from the snapshot</p>
              <ul className="mt-1 list-inside list-disc">
                {preview.absent_holdings.map((entry) => (
                  <li key={`${entry.account_id}-${entry.ticker}`}>
                    {entry.ticker} will be closed (kept with realized P&amp;L) when you
                    confirm.
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {preview.error_rows.length > 0 ? (
            <div className="mt-3 rounded-md border border-error bg-error/10 p-3 text-sm">
              <p className="font-medium">Row errors</p>
              <ul className="mt-1 list-inside list-disc">
                {preview.error_rows.map((entry) => (
                  <li key={entry.row_index}>
                    Row {entry.row_index}: {entry.errors.join("; ")}
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs opacity-70">
                Fix these rows and re-run the preview; nothing is committed while
                errors remain.
              </p>
            </div>
          ) : null}

          {preview.duplicates.length > 0 ? (
            <div className="mt-3 rounded-md border border-base-300 p-3 text-sm">
              <p className="font-medium">Duplicates (already imported; will be skipped)</p>
              <p className="mt-1 text-xs opacity-70">
                Rows {preview.duplicates.map((entry) => entry.row_index).join(", ")}
              </p>
            </div>
          ) : null}

          {preview.would_post.length > 0 ? (
            <div className="mt-3 overflow-x-auto">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Action</th>
                    <th>Account</th>
                    <th>Ticker</th>
                    <th>Quantity</th>
                    <th>Avg cost</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.would_post.map((row) => (
                    <tr key={row.row_index}>
                      <td>{row.row_index}</td>
                      <td>{row.action ?? ""}</td>
                      <td>{row.account ?? ""}</td>
                      <td>{row.ticker ?? ""}</td>
                      <td>{quantity(row.quantity_q4)}</td>
                      <td>{quantity(row.avg_cost_q4)}</td>
                      <td>{money(row.amount_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}

      {result ? (
        <section
          role="status"
          className="rounded-md border border-success bg-success/10 p-4 text-sm"
        >
          <p className="font-medium">
            Posted {result.posted}, {result.duplicate} duplicates skipped,{" "}
            {result.removed} holdings closed.
          </p>
        </section>
      ) : null}
    </main>
  );
}

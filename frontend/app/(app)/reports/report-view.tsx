import { cookies } from "next/headers";

import { apiUrl } from "@/lib/api";

type ReportResponse = {
  report: {
    kind: string;
    query?: string;
    headers?: string[];
    rows?: unknown;
    totals?: Record<string, number>;
    params?: Record<string, unknown>;
  };
};

export const REPORT_KINDS = [
  "coa",
  "summary",
  "monthly",
  "quarterly",
  "cash_flow",
  "net_worth",
] as const;

function normalizeParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function ReportView({
  requestedKind,
  searchParams,
}: {
  requestedKind: string | null;
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const kind = REPORT_KINDS.includes(
    (requestedKind ?? "") as (typeof REPORT_KINDS)[number],
  )
    ? (requestedKind as (typeof REPORT_KINDS)[number])
    : "monthly";
  const query = new URLSearchParams();
  Object.entries(searchParams).forEach(([key, rawValue]) => {
    if (key === "kind") {
      return;
    }
    const value = normalizeParam(rawValue);
    if (value !== null && value.length > 0) {
      query.set(key, value);
    }
  });

  const session = (await cookies()).get("investflow_session")?.value;
  const response = await fetch(apiUrl(`/api/reports/${kind}?${query.toString()}`), {
    method: "GET",
    cache: "no-store",
    headers: session
      ? {
          Cookie: `investflow_session=${session}`,
          "X-Requested-With": "investflow",
        }
      : {},
  });

  if (!response.ok) {
    return (
      <main className="mx-auto max-w-6xl p-6">
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="mt-2 text-error">
          Unable to load report ({kind}). Status: {response.status}
        </p>
      </main>
    );
  }

  const payload = (await response.json()) as ReportResponse;
  const report = payload.report;
  const rows = Array.isArray(report.rows) ? report.rows : [];
  const headers = report.headers ?? [];

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <p className="mt-2 text-sm opacity-80">Kind: {report.kind}</p>
      <p className="text-xs opacity-70">Query: {report.query ?? "(none)"}</p>
      <p className="text-xs opacity-70">Params: {JSON.stringify(report.params ?? {})}</p>

      {rows.length > 0 && headers.length > 0 ? (
        <div className="mt-6 overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr>
                {headers.map((header) => (
                  <th key={header}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const rowObj: Record<string, unknown> =
                  typeof row === "object" && row !== null
                    ? (row as Record<string, unknown>)
                    : { value: row };
                return (
                  <tr key={`${index}-${String(rowObj[headers[0]] ?? index)}`}>
                    {headers.map((header) => (
                      <td key={header}>{JSON.stringify(rowObj[header] ?? "")}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {report.totals ? (
        <pre className="mt-6 rounded bg-base-200 p-3 text-xs">{JSON.stringify(report.totals, null, 2)}</pre>
      ) : null}
    </main>
  );
}

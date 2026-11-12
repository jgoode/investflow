import ReportView from "./report-view";

export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const requestedKind = Array.isArray(params.kind) ? (params.kind[0] ?? null) : (params.kind ?? null);
  return <ReportView requestedKind={requestedKind} searchParams={params} />;
}

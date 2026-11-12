import ReportView from "../report-view";

export default async function ReportKindPage({
  params,
  searchParams,
}: {
  params: Promise<{ kind: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { kind } = await params;
  const query = await searchParams;
  return <ReportView requestedKind={kind} searchParams={query} />;
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_INVESTFLOW_API_BASE_URL ?? "http://localhost:8000";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

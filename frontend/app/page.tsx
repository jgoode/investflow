import { redirect } from "next/navigation";

// Route tree (docs/02-architecture.md §5.1): / → redirect /dashboard.
export default function Home() {
  return redirect("/dashboard");
}

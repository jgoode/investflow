/**
 * /dashboard placeholder — ITER-01 slice (docs/07 §4 deliverable 3).
 * The auth-gated layout arrives with ITER-02; dashboard cards with ITER-11.
 */
export default function DashboardPage() {
  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="card bg-base-200 shadow-md p-8 text-center">
        <h1 className="text-2xl font-semibold mb-2">Dashboard</h1>
        <p>Dashboard is <span data-testid="placeholder">not yet built</span>.</p>
        <p className="text-sm opacity-70 mt-2">
          Auth arrives in ITER-02 · Dashboard cards in ITER-11.
        </p>
      </div>
    </main>
  );
}

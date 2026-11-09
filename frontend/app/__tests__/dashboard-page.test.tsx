import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../(app)/dashboard/page";

const assignMock = vi.fn();

vi.mock("@/lib/dashboard-data", () => ({
  fetchDashboard: vi.fn(async () => ({
    dashboard: {
      empty: false,
      cards: {
        net_worth: { value_cents: 250000, delta_pct: 4.5, href: "/reports/net_worth?date_from=2026-01-01&date_to=2026-02-28" },
        cash_flow: { inflow_cents: 150000, outflow_cents: 80000, href: "/reports/cash_flow?date_from=2026-01-01&date_to=2026-02-28" },
        recent_transactions: { items: [{ id: 1, description: "Salary", amount_cents: 200000 }] },
      },
    },
  })),
}));

afterEach(cleanup);

beforeEach(() => {
  assignMock.mockClear();
  Object.defineProperty(window, "location", {
    value: { ...window.location, assign: assignMock },
    writable: true,
  });
});

describe("dashboard page", () => {
  it("shows the main dashboard cards on load", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /dashboard/i })).toBeTruthy();
      expect(screen.getByText(/net worth/i)).toBeTruthy();
      expect(screen.getByText(/cash flow/i)).toBeTruthy();
      expect(screen.getByText(/recent activity/i)).toBeTruthy();
    });
  });

  it("supports drill-down via context menu and double click", async () => {
    render(<DashboardPage />);

    const card = await screen.findByTestId("net-worth-card");

    fireEvent.contextMenu(card);
    expect(screen.getByRole("menuitem", { name: /open report/i })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: /copy csv/i })).toBeTruthy();

    fireEvent.doubleClick(card);
    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith("/reports/net_worth?date_from=2026-01-01&date_to=2026-02-28");
    });
  });
});

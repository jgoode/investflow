import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../(app)/dashboard/page";
import InvestmentsPage from "../(app)/investments/page";
import RootLayout from "../layout";
import Home from "../page";
import DataTable from "@/components/data-table";
import { validateLogin, validateRegister } from "@/lib/validation";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

import { redirect } from "next/navigation";

const redirectFn = vi.mocked(redirect);

afterEach(cleanup);

describe("root route (/)", () => {
  it("redirects to /dashboard (02 §5.1)", () => {
    render(<Home />);

    expect(redirectFn).toHaveBeenCalledWith("/dashboard");
  });

  it("uses the DaisyUI winter theme as the app shell default", () => {
    const html = renderToStaticMarkup(
      <RootLayout>
        <div>content</div>
      </RootLayout>,
    );

    expect(html).toContain('data-theme="winter"');
    expect(html).toContain('lang="en"');
  });
});

describe("dashboard page (/dashboard)", () => {
  it("renders the dashboard shell", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ dashboard: { empty: true, cards: {}, empty_state: { enabled: true, title: "Start your book", message: "Ready" } } }) }));
    render(<DashboardPage />);

    expect(screen.getByRole("heading", { name: /dashboard/i })).toBeTruthy();
  });
});

describe("brokerage position page", () => {
  it("loads investment accounts into a safe selector for manual trades", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ accounts: [{ id: 42, name: "Brokerage A", subtype: "brokerage" }] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ account_groups: [{ account_id: 42, account_name: "Brokerage A", total_market_value_cents: 150_000, positions: [] }], overall_total_market_value_cents: 150_000 }),
        }),
    );

    render(<InvestmentsPage />);

    expect((await screen.findAllByRole("option", { name: /brokerage a/i })).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/account/i)).toHaveProperty("tagName", "SELECT");
  });
});

describe("shared data table", () => {
  it("supports search, sorting, and paging with accessible table semantics", () => {
    const rows = [
      { id: 1, name: "Charlie", status: "active" },
      { id: 2, name: "Alpha", status: "inactive" },
      { id: 3, name: "Bravo", status: "active" },
      { id: 4, name: "Delta", status: "inactive" },
    ];

    render(
      <DataTable
        ariaLabel="Users table"
        columns={[
          { accessorKey: "name", header: "Name" },
          { accessorKey: "status", header: "Status" },
        ]}
        data={rows}
        pageSize={2}
      />,
    );

    const filterInput = screen.getByPlaceholderText(/filter rows/i);
    fireEvent.change(filterInput, { target: { value: "alp" } });

    expect(screen.queryByText("Charlie")).toBeNull();
    expect(screen.getByText("Alpha")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /sort by name/i }));
    const firstRowName = screen.getAllByRole("row")[1].querySelector("td")?.textContent;
    expect(firstRowName).toBe("Alpha");

    expect(screen.getByRole("button", { name: /next page/i })).toBeTruthy();
    expect(screen.getByText(/page 1 of 1/i)).toBeTruthy();
  });
});

describe("auth validation mirrors API constraints", () => {
  it("rejects invalid login payloads", () => {
    expect(validateLogin("Alice", "short")).toMatchObject({
      username: expect.stringMatching(/username/i),
      password: expect.stringMatching(/password/i),
    });
  });

  it("rejects register mismatch and username-in-password", () => {
    expect(validateRegister("alice", "alice-password-12", "different-password-12")).toMatchObject({
      password: expect.stringMatching(/username/i),
      passwordConfirmation: expect.stringMatching(/match/i),
    });
  });
});

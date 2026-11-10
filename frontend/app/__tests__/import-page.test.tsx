import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportPage from "../(app)/investments/import/page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/investments/import",
}));

afterEach(cleanup);

const PREVIEW_RESPONSE = {
  kind: "positions",
  total_rows: 2,
  valid_rows: 2,
  error_rows: [],
  duplicates: [],
  absent_holdings: [{ account_id: 7, ticker: "MSFT" }],
  would_post: [
    { row_index: 1, account: "Brokerage A", ticker: "AAPL", quantity_q4: 100000, avg_cost_q4: 1502500 },
  ],
};

describe("investments import center (FR-IMP-1)", () => {
  it("renders the wizard: kind, file pick, mapping and preview affordances", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ templates: [], mappings: [] }) }),
    );
    render(<ImportPage />);

    expect(screen.getByRole("heading", { name: /import/i })).toBeTruthy();
    expect(screen.getByLabelText(/Import kind/i)).toHaveProperty("tagName", "SELECT");
    expect(screen.getByLabelText(/CSV file/i)).toHaveProperty("tagName", "INPUT");
    expect(screen.getByRole("button", { name: /run preview/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /confirm import/i })).toBeTruthy();
  });

  it("shows preview results with error rows, duplicates and absent-holding flags", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ templates: [], mappings: [] }),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => PREVIEW_RESPONSE }),
    );
    render(<ImportPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /run preview/i })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /run preview/i }));

    await waitFor(() => expect(screen.getByText(/AAPL/)).toBeTruthy());
    expect(screen.getByText(/MSFT/i)).toBeTruthy(); // absent-holding flag surfaces in preview
  });

  it("runs the confirmed import through the commit endpoint with confirm flags", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ templates: [], mappings: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => PREVIEW_RESPONSE })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          counts: { posted: 2, duplicate: 0, removed: 1 },
          results: [],
        }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<ImportPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /run preview/i })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /run preview/i }));
    await waitFor(() => screen.getByRole("button", { name: /confirm import/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm import/i }));

    await waitFor(() => expect(screen.getByText(/posted/i)).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

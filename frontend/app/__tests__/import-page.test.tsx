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

const PRICE_TEMPLATE = {
  name: "bank statement",
  kind: "price_history",
  column_mapping: { date: "Date", ticker: "Ticker", close: "Close", volume: "Volume" },
};

const PRICE_PREVIEW_RESPONSE = {
  kind: "price_history",
  total_rows: 2,
  valid_rows: 2,
  error_rows: [],
  duplicates: [],
  absent_holdings: [],
  would_post: [
    {
      row_index: 1,
      action: "price",
      ticker: "MSFT",
      date: "2024-01-02",
      close_q4: 3725000,
      volume: 24850000,
    },
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

  // --- ITER-23 / AC-IMP1h: price_history kind in the wizard -----------------------

  it("offers the price history kind with the bank statement template hint", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ templates: [PRICE_TEMPLATE], mappings: [] }),
        }),
    );
    render(<ImportPage />);

    const kindSelect = screen.getByLabelText(/Import kind/i);
    const options = Array.from(kindSelect.querySelectorAll("option")).map(
      (option) => option.value,
    );
    expect(options).toContain("price_history");

    fireEvent.change(kindSelect, { target: { value: "price_history" } });

    await waitFor(() =>
      expect(screen.getByText(/bank statement/i)).toBeTruthy(),
    );
  });

  it("previews a price history import showing date/close/volume effects", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, json: async () => ({ templates: [], mappings: [] }) })
        .mockResolvedValueOnce({ ok: true, json: async () => PRICE_PREVIEW_RESPONSE }),
    );
    render(<ImportPage />);

    const kindSelect = screen.getByLabelText(/Import kind/i);
    fireEvent.change(kindSelect, { target: { value: "price_history" } });
    await waitFor(() => expect(screen.getByRole("button", { name: /run preview/i })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /run preview/i }));

    await waitFor(() => expect(screen.getByText(/2024-01-02/)).toBeTruthy());
    expect(screen.getByRole("cell", { name: "price" })).toBeTruthy(); // action column surfaces the price effect
  });
});

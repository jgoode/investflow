import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../(app)/dashboard/page";
import InvestmentsPage from "../(app)/investments/page";
import Home from "../page";
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

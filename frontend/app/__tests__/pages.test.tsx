/**
 * L3 unit tests — ITER-01 frontend slice (docs/07 §4).
 *
 * ACs under test:
 *   - root page redirects to /dashboard (docs/02-architecture.md §5.1 route tree)
 *   - /dashboard shows a placeholder saying "not yet built" (docs/07 §4 deliverable 3)
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../dashboard/page";
import Home from "../page";

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

describe("dashboard placeholder (/dashboard)", () => {
  it("states the dashboard is not yet built", () => {
    render(<DashboardPage />);

    expect(screen.getByText(/not yet built/i)).toBeTruthy();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../(app)/dashboard/page";
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

describe("dashboard placeholder (/dashboard)", () => {
  it("states the dashboard is not yet built", () => {
    render(<DashboardPage />);

    expect(screen.getByText(/not yet built/i)).toBeTruthy();
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

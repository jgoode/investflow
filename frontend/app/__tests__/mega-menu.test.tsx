import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MegaMenu } from "../(app)/mega-menu";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push, refresh }),
}));

afterEach(cleanup);

describe("mega menu", () => {
  it("renders the nav directly and keeps route highlight with escape close", () => {
    render(<MegaMenu username="alice" />);

    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(nav).toBeTruthy();
    expect(screen.getByRole("link", { name: "InvestFlow home" }).getAttribute("href")).toBe(
      "/dashboard",
    );

    const dashboard = screen.getByRole("link", { name: "Dashboard" });
    expect(dashboard.getAttribute("aria-current")).toBe("page");

    fireEvent.focus(screen.getByRole("link", { name: "Accounts" }));
    expect(screen.getByRole("link", { name: "Chart of Accounts" }).getAttribute("href")).toBe(
      "/accounts",
    );

    fireEvent.keyDown(nav, { key: "Escape" });
    expect(screen.queryByRole("link", { name: "Chart of Accounts" })).toBeNull();
  });

  it("uses the required horizontal top-level IA and submenu route bindings", () => {
    render(<MegaMenu username="alice" />);

    const topLevelLinks = Array.from(screen.getAllByRole("link")).filter((link) =>
      ["Dashboard", "Accounts", "Investments", "Reporting", "Settings"].includes(
        link.textContent?.trim() ?? "",
      ),
    );
    expect(topLevelLinks.map((link) => link.textContent?.trim())).toEqual([
      "Dashboard",
      "Accounts",
      "Investments",
      "Reporting",
      "Settings",
    ]);

    expect(screen.getByRole("link", { name: "Dashboard" }).getAttribute("href")).toBe("/dashboard");
    expect(screen.getByRole("link", { name: "Accounts" }).getAttribute("href")).toBe("/accounts");
    expect(screen.getByRole("link", { name: "Investments" }).getAttribute("href")).toBe("/investments");
    expect(screen.getByRole("link", { name: "Reporting" }).getAttribute("href")).toBe("/reports");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("href")).toBe("/settings");

    fireEvent.focus(screen.getByRole("link", { name: "Accounts" }));
    expect(screen.getByRole("link", { name: "Chart of Accounts" }).getAttribute("href")).toBe("/accounts");
    expect(screen.getByRole("link", { name: "Categories" }).getAttribute("href")).toBe("/categories");
    expect(screen.getByRole("link", { name: "Transactions" }).getAttribute("href")).toBe("/transactions");

    fireEvent.focus(screen.getByRole("link", { name: "Investments" }));
    expect(screen.getByRole("link", { name: "Portfolio" }).getAttribute("href")).toBe("/investments");
    expect(screen.getByRole("link", { name: "Analysis" }).getAttribute("href")).toBe("/investments");
    expect(screen.getByRole("link", { name: "Research" }).getAttribute("href")).toBe("/investments");

    fireEvent.focus(screen.getByRole("link", { name: "Settings" }));
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Posting" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Seed Management" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Backup and Downloads" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Users" }).getAttribute("href")).toBe("/users");
    expect(screen.getByRole("link", { name: "Audit" }).getAttribute("href")).toBe("/settings");
  });

  it("returns focus to the group trigger when Escape closes the submenu (AC-N2/AC-X4d)", () => {
    render(<MegaMenu username="alice" />);

    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const accounts = screen.getByRole("link", { name: "Accounts" });
    fireEvent.focus(accounts);
    expect(screen.getByRole("link", { name: "Chart of Accounts" })).toBeTruthy();

    fireEvent.keyDown(nav, { key: "Escape" });
    expect(screen.queryByRole("link", { name: "Chart of Accounts" })).toBeNull();
    expect(document.activeElement).toBe(accounts);
  });

  it("uses a hover-safe close delay so pointer travel must not collapse the submenu (AC-X4d)", async () => {
    render(<MegaMenu username="alice" />);

    const investments = screen.getByRole("link", { name: "Investments" });
    fireEvent.focus(investments);
    expect(screen.getByRole("link", { name: "Analysis" })).toBeTruthy();

    const li = investments.closest("li") as HTMLElement;
    const submenu = screen.getByRole("link", { name: "Analysis" }).closest("ul") as HTMLElement;

    // Leaving the group immediately must not close the submenu yet (delay window).
    fireEvent.mouseLeave(li);
    expect(screen.getByRole("link", { name: "Analysis" })).toBeTruthy();

    // Moving into the submenu cancels the pending close.
    fireEvent.mouseEnter(submenu);
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(screen.getByRole("link", { name: "Analysis" })).toBeTruthy();

    // Leaving again (with no re-entry) closes it after the delay.
    fireEvent.mouseLeave(submenu);
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(screen.queryByRole("link", { name: "Analysis" })).toBeNull();
  });

  it("stays keyboard-reachable after hover interaction and highlights the active item", () => {
    render(<MegaMenu username="alice" />);

    const investments = screen.getByRole("link", { name: "Investments" });
    const li = investments.closest("li") as HTMLElement;
    fireEvent.mouseEnter(li);
    const analysis = screen.getByRole("link", { name: "Analysis" });
    expect(analysis).toBeTruthy();

    // Keyboard focus must still be able to open and use the submenu after hover.
    fireEvent.focus(analysis);
    expect(analysis.getAttribute("aria-current")).toBeNull();

    const portfolio = screen.getByRole("link", { name: "Portfolio" });
    expect(portfolio).toBeTruthy();
  });
});

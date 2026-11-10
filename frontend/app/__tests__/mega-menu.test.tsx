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
  it("opens and closes with escape and keeps route highlight", () => {
    render(<MegaMenu username="alice" />);

    const trigger = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(trigger);

    const dashboard = screen.getByRole("link", { name: "Dashboard" });
    expect(dashboard.getAttribute("aria-current")).toBe("page");

    const accountsToggle = screen.getByRole("button", { name: "Toggle Accounts submenu" });
    fireEvent.click(accountsToggle);
    expect(screen.getByRole("link", { name: "Chart of Accounts" }).getAttribute("href")).toBe(
      "/accounts",
    );

    fireEvent.keyDown(screen.getByRole("navigation"), { key: "Escape" });
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("uses the required parent/child IA and reachable submenu routes", () => {
    render(<MegaMenu username="alice" />);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.getByRole("link", { name: "Dashboard" }).getAttribute("href")).toBe("/dashboard");
    expect(screen.getByRole("link", { name: "Accounts" }).getAttribute("href")).toBe("/accounts");
    expect(screen.getByRole("link", { name: "Investments" }).getAttribute("href")).toBe("/investments");
    expect(screen.getByRole("link", { name: "Reporting" }).getAttribute("href")).toBe("/reports");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("href")).toBe("/settings");

    fireEvent.click(screen.getByRole("button", { name: "Toggle Accounts submenu" }));
    expect(screen.getByRole("link", { name: "Chart of Accounts" }).getAttribute("href")).toBe("/accounts");
    expect(screen.getByRole("link", { name: "Categories" }).getAttribute("href")).toBe("/categories");
    expect(screen.getByRole("link", { name: "Transactions" }).getAttribute("href")).toBe("/transactions");

    fireEvent.click(screen.getByRole("button", { name: "Toggle Investments submenu" }));
    expect(screen.getByRole("link", { name: "Portfolio Research" }).getAttribute("href")).toBe("/investments");
    expect(screen.getByRole("link", { name: "Analysis" }).getAttribute("href")).toBe("/investments");

    fireEvent.click(screen.getByRole("button", { name: "Toggle Settings submenu" }));
    expect(screen.getByRole("link", { name: "Profile" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Posting" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Seed Management" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Backup and Download" }).getAttribute("href")).toBe("/settings");
    expect(screen.getByRole("link", { name: "Users" }).getAttribute("href")).toBe("/users");
    expect(screen.getByRole("link", { name: "Audit" }).getAttribute("href")).toBe("/settings");
  });
});

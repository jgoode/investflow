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

    fireEvent.keyDown(screen.getByRole("navigation"), { key: "Escape" });
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("shows Users as an enabled destination", () => {
    render(<MegaMenu username="alice" />);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));

    const usersLink = screen.getByRole("link", { name: "Users" });
    expect(usersLink).toBeTruthy();
    expect(screen.queryByText("Users (coming)")).toBeNull();
  });
});

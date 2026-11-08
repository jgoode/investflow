import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MegaMenu } from "../(app)/mega-menu";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push, refresh }),
}));

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
});

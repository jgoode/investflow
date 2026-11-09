"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { apiUrl } from "@/lib/api";

const GROUPS = [
  { key: "dashboard", label: "Dashboard", href: "/dashboard", enabled: true },
  { key: "reports", label: "Reports", href: "/reports", enabled: true },
  { key: "accounts", label: "Accounts", href: "/accounts", enabled: true },
  { key: "transactions", label: "Transactions", href: "/transactions", enabled: true },
  { key: "categories", label: "Categories", href: "/categories", enabled: true },
  { key: "investments", label: "Investments", href: "/investments", enabled: true },
  { key: "users", label: "Users", href: "/users", enabled: true },
  { key: "settings", label: "Settings", href: "/settings", enabled: false },
] as const;

export function MegaMenu({ username }: { username: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  async function onLogout() {
    await fetch(apiUrl("/api/auth/logout"), {
      method: "POST",
      credentials: "include",
      headers: {
        "X-Requested-With": "investflow",
      },
    });
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-base-300 bg-base-100 px-4 py-3">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
        <div className="relative">
          <button
            ref={triggerRef}
            type="button"
            className="btn btn-outline btn-sm min-h-11"
            aria-expanded={open}
            aria-controls="mega-menu-content"
            onClick={() => setOpen((value) => !value)}
          >
            Menu
          </button>
          {open ? (
            <nav
              id="mega-menu-content"
              className="absolute left-0 z-20 mt-2 w-[28rem] rounded-lg border border-base-300 bg-base-100 p-4 shadow-lg"
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setOpen(false);
                  triggerRef.current?.focus();
                }
              }}
            >
              <ul className="grid grid-cols-2 gap-2">
                {GROUPS.map((group) => {
                  const active = pathname.startsWith(group.href);
                  if (!group.enabled) {
                    return (
                      <li key={group.key} className="rounded-md bg-base-200 px-3 py-2 text-sm opacity-65">
                        {group.label} <span className="ml-1 text-xs">(coming)</span>
                      </li>
                    );
                  }
                  return (
                    <li key={group.key}>
                      <Link
                        className={`block rounded-md px-3 py-2 text-sm min-h-11 ${
                          active ? "bg-primary text-primary-content" : "hover:bg-base-200"
                        }`}
                        aria-current={active ? "page" : undefined}
                        href={group.href}
                        onClick={() => setOpen(false)}
                      >
                        {group.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm opacity-70">{username}</span>
          <button type="button" className="btn btn-ghost btn-sm min-h-11" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}

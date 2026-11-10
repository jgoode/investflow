"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { apiUrl } from "@/lib/api";

type MenuItem = {
  key: string;
  label: string;
  href: string;
};

type MenuGroup = {
  key: string;
  label: string;
  href: string;
  items?: MenuItem[];
};

const MENU_GROUPS: MenuGroup[] = [
  { key: "dashboard", label: "Dashboard", href: "/dashboard" },
  {
    key: "accounts",
    label: "Accounts",
    href: "/accounts",
    items: [
      { key: "chart-of-accounts", label: "Chart of Accounts", href: "/accounts" },
      { key: "categories", label: "Categories", href: "/categories" },
      { key: "transactions", label: "Transactions", href: "/transactions" },
    ],
  },
  {
    key: "investments",
    label: "Investments",
    href: "/investments",
    items: [
      { key: "portfolio-research", label: "Portfolio Research", href: "/investments" },
      { key: "analysis", label: "Analysis", href: "/investments" },
    ],
  },
  { key: "reporting", label: "Reporting", href: "/reports" },
  {
    key: "settings",
    label: "Settings",
    href: "/settings",
    items: [
      { key: "profile", label: "Profile", href: "/settings" },
      { key: "posting", label: "Posting", href: "/settings" },
      { key: "seed-management", label: "Seed Management", href: "/settings" },
      { key: "backup-and-download", label: "Backup and Download", href: "/settings" },
      { key: "users", label: "Users", href: "/users" },
      { key: "audit", label: "Audit", href: "/settings" },
    ],
  },
];

function isRouteActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function MegaMenu({ username }: { username: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(() => {
    const activeGroup = MENU_GROUPS.find((group) => {
      if (group.items) {
        return group.items.some((item) => isRouteActive(pathname, item.href));
      }
      return isRouteActive(pathname, group.href);
    });
    return activeGroup?.key ?? null;
  });
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
              aria-label="Primary navigation"
              className="absolute left-0 z-20 mt-2 w-[30rem] rounded-lg border border-base-300 bg-base-100 p-4 shadow-lg"
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setOpen(false);
                  setOpenGroup(null);
                  triggerRef.current?.focus();
                }
              }}
            >
              <ul className="space-y-3">
                {MENU_GROUPS.map((group) => {
                  const items = group.items ?? [];
                  const hasItems = items.length > 0;
                  const groupIsActive = hasItems
                    ? items.some((item) => isRouteActive(pathname, item.href)) ||
                      isRouteActive(pathname, group.href)
                    : isRouteActive(pathname, group.href);
                  const groupIsOpen = openGroup === group.key || (hasItems && groupIsActive && open);

                  return (
                    <li key={group.key} className="rounded-md border border-base-200 px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Link
                          className={`min-h-11 flex-1 rounded-md px-2 py-2 text-sm font-medium ${
                            groupIsActive ? "bg-primary text-primary-content" : "hover:bg-base-200"
                          }`}
                          aria-current={groupIsActive ? "page" : undefined}
                          href={group.href}
                          onClick={() => {
                            setOpen(false);
                            setOpenGroup(null);
                          }}
                        >
                          {group.label}
                        </Link>
                        {hasItems ? (
                          <button
                            type="button"
                            className="btn btn-ghost btn-xs min-h-11 min-w-11"
                            aria-label={`Toggle ${group.label} submenu`}
                            aria-expanded={groupIsOpen}
                            aria-controls={`${group.key}-submenu`}
                            onClick={() => {
                              setOpenGroup((current) => (current === group.key ? null : group.key));
                            }}
                          >
                            {groupIsOpen ? "−" : "+"}
                          </button>
                        ) : null}
                      </div>

                      {hasItems && groupIsOpen ? (
                        <ul id={`${group.key}-submenu`} className="mt-2 ml-3 space-y-2 border-l border-base-300 pl-3">
                          {items.map((item) => {
                            const itemIsActive = isRouteActive(pathname, item.href);

                            return (
                              <li key={item.key}>
                                <Link
                                  className={`block min-h-11 rounded-md px-2 py-2 text-sm ${
                                    itemIsActive ? "bg-primary text-primary-content" : "hover:bg-base-200"
                                  }`}
                                  aria-current={itemIsActive ? "page" : undefined}
                                  href={item.href}
                                  onClick={() => {
                                    setOpen(false);
                                    setOpenGroup(group.key);
                                  }}
                                >
                                  {item.label}
                                </Link>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
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

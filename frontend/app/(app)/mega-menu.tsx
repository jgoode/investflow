"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

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
      { key: "portfolio", label: "Portfolio", href: "/investments" },
      { key: "analysis", label: "Analysis", href: "/investments" },
      { key: "research", label: "Research", href: "/investments" },
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
      { key: "backup-and-downloads", label: "Backup and Downloads", href: "/settings" },
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
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [openGroup, setOpenGroup] = useState<string | null>(() => {
    const activeGroup = MENU_GROUPS.find((group) => {
      if (group.items) {
        return group.items.some((item) => isRouteActive(pathname, item.href));
      }
      return isRouteActive(pathname, group.href);
    });
    return activeGroup?.key ?? null;
  });

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

  function handleGroupFocus(groupKey: string) {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setOpenGroup(groupKey);
  }

  function handleGroupLeave(groupKey: string) {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = setTimeout(() => {
      setOpenGroup((current) => (current === groupKey ? null : current));
      closeTimerRef.current = null;
    }, 120);
  }

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  return (
    <header className="border-b border-base-300 bg-base-100 px-4 py-3">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
        <Link
          href="/dashboard"
          className="min-h-11 rounded-md px-2 py-2 text-lg font-semibold tracking-tight hover:bg-base-200"
          aria-label="InvestFlow home"
        >
          InvestFlow
        </Link>
        <nav
          aria-label="Primary navigation"
          className="relative flex-1"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpenGroup(null);
            }
          }}
        >
          <ul className="flex flex-wrap items-start gap-2">
            {MENU_GROUPS.map((group) => {
              const items = group.items ?? [];
              const hasItems = items.length > 0;
              const groupIsActive = hasItems
                ? items.some((item) => isRouteActive(pathname, item.href)) || isRouteActive(pathname, group.href)
                : isRouteActive(pathname, group.href);
              const groupIsOpen = openGroup === group.key;

              return (
                <li
                  key={group.key}
                  className="relative"
                  onMouseEnter={() => hasItems && handleGroupFocus(group.key)}
                  onMouseLeave={() => hasItems && handleGroupLeave(group.key)}
                >
                  <div className="flex items-center rounded-md border border-base-200 bg-base-100">
                    <Link
                      className={`min-h-11 rounded-l-md px-3 py-2 text-sm font-medium ${
                        groupIsActive ? "bg-primary text-primary-content" : "hover:bg-base-200"
                      }`}
                      aria-current={groupIsActive ? "page" : undefined}
                      href={group.href}
                      onClick={() => {
                        setOpenGroup(null);
                      }}
                      onFocus={() => hasItems && handleGroupFocus(group.key)}
                    >
                      {group.label}
                    </Link>
                    {hasItems ? (
                      <span className="sr-only">{group.label} submenu</span>
                    ) : null}
                  </div>

                  {hasItems && groupIsOpen ? (
                    <ul
                      id={`${group.key}-submenu`}
                      className="absolute left-0 top-full z-10 mt-0 min-w-52 rounded-md border border-base-300 bg-base-100 p-2 shadow-lg"
                      onMouseEnter={() => handleGroupFocus(group.key)}
                      onMouseLeave={() => handleGroupLeave(group.key)}
                    >
                      {items.map((item) => {
                        const itemIsActive = isRouteActive(pathname, item.href);

                        return (
                          <li key={item.key}>
                            <Link
                              className={`block min-h-11 rounded-md px-3 py-2 text-sm ${
                                itemIsActive ? "bg-primary text-primary-content" : "hover:bg-base-200"
                              }`}
                              aria-current={itemIsActive ? "page" : undefined}
                              href={item.href}
                              onClick={() => {
                                setOpenGroup(group.key);
                              }}
                              onFocus={() => handleGroupFocus(group.key)}
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

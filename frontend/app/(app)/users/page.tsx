"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import DataTable from "@/components/data-table";
import { apiUrl } from "@/lib/api";

type UserRow = {
  id: number;
  username: string;
  display_name: string | null;
  is_active: boolean;
  created_at: number | null;
  last_login_at: number | null;
};

type MePayload = { user: UserRow };
type UsersPayload = { users: UserRow[] };

function ts(value: number | null): string {
  if (!value) return "—";
  return new Date(value * 1000).toLocaleString();
}

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [me, setMe] = useState<UserRow | null>(null);
  const [displayDrafts, setDisplayDrafts] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    oldPassword: "",
    newPassword: "",
    confirm: "",
  });

  const fetchUsersAndMe = useCallback(async (): Promise<void> => {
    const [meResp, usersResp] = await Promise.all([
      fetch(apiUrl("/api/auth/me"), { credentials: "include" }),
      fetch(apiUrl("/api/users"), { credentials: "include" }),
    ]);
    if (meResp.status === 401 || usersResp.status === 401) {
      router.push("/login");
      return;
    }
    const meJson = (await meResp.json()) as MePayload;
    const usersJson = (await usersResp.json()) as UsersPayload;
    setMe(meJson.user);
    setUsers(usersJson.users);
    setDisplayDrafts(
      Object.fromEntries(usersJson.users.map((row) => [row.id, row.display_name ?? ""])),
    );
  }, [router]);

  useEffect(() => {
    void fetchUsersAndMe();
  }, [fetchUsersAndMe]);

  const sortedUsers = useMemo(
    () => [...users].sort((a, b) => a.username.localeCompare(b.username)),
    [users],
  );

  async function patchUser(userId: number, payload: Record<string, unknown>): Promise<void> {
    setError(null);
    setMessage(null);
    const resp = await fetch(apiUrl(`/api/users/${userId}`), {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const body = (await resp.json()) as { detail?: string };
      setError(body.detail ?? "Update failed");
      return;
    }
    await fetchUsersAndMe();
    setMessage("User updated.");
  }

  async function softDeleteUser(userId: number): Promise<void> {
    setError(null);
    setMessage(null);
    const resp = await fetch(apiUrl(`/api/users/${userId}`), {
      method: "DELETE",
      credentials: "include",
      headers: {
        "X-Requested-With": "investflow",
      },
    });
    if (!resp.ok) {
      const body = (await resp.json()) as { detail?: string };
      setError(body.detail ?? "Delete failed");
      return;
    }
    await fetchUsersAndMe();
    setMessage("User deactivated.");
  }

  async function changePassword(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const resp = await fetch(apiUrl("/api/users/me/password"), {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({
        old_password: passwordForm.oldPassword,
        new_password: passwordForm.newPassword,
        new_password_confirmation: passwordForm.confirm,
      }),
    });
    if (!resp.ok) {
      const body = (await resp.json()) as { detail?: string };
      setError(body.detail ?? "Password update failed");
      return;
    }
    setPasswordForm({ oldPassword: "", newPassword: "", confirm: "" });
    setMessage("Password changed.");
    await fetchUsersAndMe();
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Users</h1>
      <p className="mt-2 text-sm opacity-70">Shared-book visibility for all users.</p>
      {message ? <p className="mt-4 text-success">{message}</p> : null}
      {error ? <p className="mt-4 text-error">{error}</p> : null}

      <div className="mt-6">
        <DataTable
          ariaLabel="Users table"
          columns={[
            { accessorKey: "username", header: "Username" },
            {
              accessorKey: "display_name",
              header: "Display name",
              cell: (row) => (
                <input
                  className="input input-bordered input-sm min-h-11 w-full max-w-xs"
                  value={displayDrafts[row.id] ?? ""}
                  onChange={(event) =>
                    setDisplayDrafts((prev) => ({ ...prev, [row.id]: event.target.value }))
                  }
                />
              ),
            },
            {
              accessorKey: "is_active",
              header: "Active",
              cell: (row) => (row.is_active ? "yes" : "no"),
            },
            {
              accessorKey: "created_at",
              header: "Created",
              cell: (row) => ts(row.created_at),
            },
            {
              accessorKey: "last_login_at",
              header: "Last login",
              cell: (row) => ts(row.last_login_at),
            },
            {
              accessorKey: "id",
              header: "Actions",
              sortable: false,
              cell: (row) => {
                const isSelf = me?.id === row.id;
                return (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn btn-xs min-h-11"
                      onClick={() =>
                        patchUser(row.id, {
                          display_name: displayDrafts[row.id] || null,
                        })
                      }
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="btn btn-xs min-h-11"
                      disabled={isSelf}
                      onClick={() => patchUser(row.id, { is_active: !row.is_active })}
                    >
                      {row.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-xs btn-error min-h-11"
                      disabled={isSelf}
                      onClick={() => softDeleteUser(row.id)}
                    >
                      Delete
                    </button>
                  </div>
                );
              },
            },
          ]}
          data={sortedUsers}
          pageSize={10}
        />
      </div>

      <section className="mt-8 max-w-md">
        <h2 className="text-xl font-semibold">Change password</h2>
        <form className="mt-3 space-y-3" onSubmit={changePassword}>
          <label className="form-control">
            <span className="label-text">Current password</span>
            <input
              type="password"
              className="input input-bordered min-h-11"
              value={passwordForm.oldPassword}
              onChange={(event) =>
                setPasswordForm((prev) => ({ ...prev, oldPassword: event.target.value }))
              }
            />
          </label>
          <label className="form-control">
            <span className="label-text">New password</span>
            <input
              type="password"
              className="input input-bordered min-h-11"
              value={passwordForm.newPassword}
              onChange={(event) =>
                setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))
              }
            />
          </label>
          <label className="form-control">
            <span className="label-text">Confirm new password</span>
            <input
              type="password"
              className="input input-bordered min-h-11"
              value={passwordForm.confirm}
              onChange={(event) =>
                setPasswordForm((prev) => ({ ...prev, confirm: event.target.value }))
              }
            />
          </label>
          <button type="submit" className="btn btn-primary min-h-11">
            Change password
          </button>
        </form>
      </section>
    </main>
  );
}

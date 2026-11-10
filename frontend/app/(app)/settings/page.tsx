"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiUrl } from "@/lib/api";

type SettingsMap = Record<string, string | number | boolean | null>;

const SECTION_CLASS = "rounded-xl border border-base-300 bg-base-100 p-4 shadow-sm";

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<SettingsMap>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl("/api/settings"), {
        credentials: "include",
        headers: {
          "X-Requested-With": "investflow",
        },
      });
      if (resp.status === 401) {
        router.push("/login");
        return;
      }
      if (!resp.ok) {
        throw new Error("Unable to load settings");
      }
      const json = (await resp.json()) as { settings?: SettingsMap };
      setSettings(json.settings ?? {});
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to load settings");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  async function patchSetting(key: string, value: string | number | boolean | null) {
    setError(null);
    setMessage(null);
    const resp = await fetch(apiUrl("/api/settings"), {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "investflow",
      },
      body: JSON.stringify({ settings: { [key]: value } }),
    });
    if (!resp.ok) {
      const body = (await resp.json().catch(() => ({}))) as { detail?: string };
      setError(body.detail ?? "Update failed");
      return;
    }
    const json = (await resp.json()) as { settings?: SettingsMap };
    setSettings(json.settings ?? {});
    setMessage("Saved.");
  }

  async function downloadBackup() {
    const resp = await fetch(apiUrl("/api/settings/backup"), {
      credentials: "include",
      headers: {
        "X-Requested-With": "investflow",
      },
    });
    if (!resp.ok) {
      setError("Backup download failed");
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `investflow-backup-${Date.now()}.db`;
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("Backup downloaded.");
  }

  async function applySeed() {
    setError(null);
    setMessage(null);
    const resp = await fetch(apiUrl("/api/settings/seed/apply"), {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "investflow" },
    });
    if (!resp.ok) {
      setError("Seed apply failed");
      return;
    }
    setMessage("Seed re-applied.");
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm opacity-70">Profile, defaults, provider config, backups, and audit log.</p>
      </header>

      {error ? <div className="alert alert-error min-h-11">{error}</div> : null}
      {message ? <div className="alert alert-success min-h-11">{message}</div> : null}
      {loading ? <div className="text-sm opacity-70">Loading settings…</div> : null}

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Profile</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="form-control">
            <span className="label-text">Display name</span>
            <input
              className="input input-bordered min-h-11"
              value={String(settings["profile.display_name"] ?? "")}
              onChange={(event) =>
                setSettings((prev) => ({ ...prev, "profile.display_name": event.target.value }))
              }
              onBlur={() =>
                void patchSetting("profile.display_name", String(settings["profile.display_name"] ?? ""))
              }
            />
          </label>
          <label className="form-control">
            <span className="label-text">Currency</span>
            <input
              className="input input-bordered min-h-11"
              value={String(settings.currency ?? "USD")}
              onChange={(event) => setSettings((prev) => ({ ...prev, currency: event.target.value }))}
              onBlur={() => void patchSetting("currency", String(settings.currency ?? "USD"))}
            />
          </label>
        </div>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Provider defaults</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="form-control">
            <span className="label-text">Provider</span>
            <select
              className="select select-bordered min-h-11"
              value={String(settings["provider.selected"] ?? "yahoo")}
              onChange={(event) => {
                const value = event.target.value;
                void patchSetting("provider.selected", value);
              }}
            >
              <option value="yahoo">Yahoo Finance</option>
              <option value="manual">Manual fallback</option>
            </select>
          </label>
          <div className="rounded-lg bg-base-200 p-3 text-sm">
            Unofficial data source. Manual entries remain available and take precedence when newer
            provider data is unavailable.
          </div>
        </div>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Posting defaults</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="form-control">
            <span className="label-text">Future posting window (days)</span>
            <input
              type="number"
              min={0}
              max={30}
              className="input input-bordered min-h-11"
              value={Number(settings["posting.default_window_days"] ?? 0)}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  "posting.default_window_days": Number(event.target.value),
                }))
              }
              onBlur={() =>
                void patchSetting(
                  "posting.default_window_days",
                  Number(settings["posting.default_window_days"] ?? 0),
                )
              }
            />
          </label>
          <label className="form-control">
            <span className="label-text">Default rounding</span>
            <select
              className="select select-bordered min-h-11"
              value={String(settings["ui.rounding_mode"] ?? "round-half-up")}
              onChange={(event) => void patchSetting("ui.rounding_mode", event.target.value)}
            >
              <option value="round-half-up">Round half up</option>
              <option value="floor">Floor</option>
            </select>
          </label>
        </div>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Seed management</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" className="btn btn-primary min-h-11" onClick={() => void applySeed()}>
            Apply seed additions
          </button>
          <span className="self-center text-sm opacity-70">Seed version remains idempotent.</span>
        </div>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Backup & download</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" className="btn btn-secondary min-h-11" onClick={() => void downloadBackup()}>
            Download SQLite backup
          </button>
          <span className="self-center text-sm opacity-70">Restore remains manual; this is download-only.</span>
        </div>
      </section>

      <section className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold">Audit log</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr>
                <th>When</th>
                <th>User</th>
                <th>Action</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={4} className="text-sm opacity-70">
                  Audit entries appear here once recorded from settings and ledger actions.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

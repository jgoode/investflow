"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiUrl } from "@/lib/api";
import { validateLogin } from "@/lib/validation";

type LoginResponse = {
  detail?: string | Array<{ loc: (string | number)[]; msg: string }>;
};

export default function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fieldErrors = validateLogin(username, password);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (Object.keys(fieldErrors).length > 0) {
      setError("Please fix the highlighted fields.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(apiUrl("/api/auth/login"), {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "investflow",
        },
        body: JSON.stringify({ username, password }),
      });
      if (response.ok) {
        router.push("/dashboard");
        router.refresh();
        return;
      }

      const payload = (await response.json()) as LoginResponse;
      if (typeof payload.detail === "string") {
        setError(payload.detail);
        return;
      }
      setError("Unable to login.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md items-center p-4">
      <div className="card w-full bg-base-200 p-6 shadow-md">
        <h1 className="text-xl font-semibold">Login</h1>
        <form className="mt-4 space-y-4" onSubmit={onSubmit}>
          <label className="form-control">
            <span className="label-text">Username</span>
            <input
              className="input input-bordered min-h-11"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              name="username"
            />
            {fieldErrors.username ? <span className="text-error text-sm">{fieldErrors.username}</span> : null}
          </label>
          <label className="form-control">
            <span className="label-text">Password</span>
            <input
              className="input input-bordered min-h-11"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              name="password"
            />
            {fieldErrors.password ? <span className="text-error text-sm">{fieldErrors.password}</span> : null}
          </label>
          {error ? <p className="text-error text-sm">{error}</p> : null}
          <button className="btn btn-primary min-h-11 w-full" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}

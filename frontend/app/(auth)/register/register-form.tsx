"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiUrl } from "@/lib/api";
import { validateRegister } from "@/lib/validation";

type RegisterResponse = {
  detail?: string | Array<{ loc: (string | number)[]; msg: string }>;
};

function flattenValidationErrors(
  detail: Array<{ loc: (string | number)[]; msg: string }>,
): string {
  return detail.map((entry) => entry.msg).join(", ");
}

export default function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fieldErrors = validateRegister(username, password, passwordConfirmation);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (Object.keys(fieldErrors).length > 0) {
      setError("Please fix the highlighted fields.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(apiUrl("/api/auth/register"), {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "investflow",
        },
        body: JSON.stringify({
          username,
          password,
          password_confirmation: passwordConfirmation,
          display_name: displayName || null,
        }),
      });
      if (response.ok) {
        router.push("/dashboard");
        router.refresh();
        return;
      }

      const payload = (await response.json()) as RegisterResponse;
      if (typeof payload.detail === "string") {
        setError(payload.detail);
        return;
      }
      if (Array.isArray(payload.detail)) {
        setError(flattenValidationErrors(payload.detail));
        return;
      }
      setError("Unable to register.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md items-center p-4">
      <div className="card w-full bg-base-200 p-6 shadow-md">
        <h1 className="text-xl font-semibold">Register</h1>
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
            <span className="label-text">Display name (optional)</span>
            <input
              className="input input-bordered min-h-11"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
              name="display_name"
            />
          </label>
          <label className="form-control">
            <span className="label-text">Password</span>
            <input
              className="input input-bordered min-h-11"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              name="password"
            />
            {fieldErrors.password ? <span className="text-error text-sm">{fieldErrors.password}</span> : null}
          </label>
          <label className="form-control">
            <span className="label-text">Password confirmation</span>
            <input
              className="input input-bordered min-h-11"
              type="password"
              value={passwordConfirmation}
              onChange={(event) => setPasswordConfirmation(event.target.value)}
              autoComplete="new-password"
              name="password_confirmation"
            />
            {fieldErrors.passwordConfirmation ? (
              <span className="text-error text-sm">{fieldErrors.passwordConfirmation}</span>
            ) : null}
          </label>
          {error ? <p className="text-error text-sm">{error}</p> : null}
          <button className="btn btn-primary min-h-11 w-full" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Creating..." : "Create account"}
          </button>
        </form>
      </div>
    </main>
  );
}

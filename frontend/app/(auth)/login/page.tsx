import Link from "next/link";
import { redirect } from "next/navigation";

import { getSessionUser } from "@/lib/auth-session";

import LoginForm from "./login-form";

export default async function LoginPage() {
  const sessionUser = await getSessionUser();
  if (sessionUser) {
    redirect("/dashboard");
  }

  return (
    <>
      <LoginForm />
      <p className="mt-[-5rem] pb-8 text-center text-sm">
        Need an account? <Link className="link link-primary" href="/register">Register</Link>
      </p>
    </>
  );
}

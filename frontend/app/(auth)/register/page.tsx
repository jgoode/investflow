import Link from "next/link";
import { redirect } from "next/navigation";

import { getSessionUser } from "@/lib/auth-session";

import RegisterForm from "./register-form";

export default async function RegisterPage() {
  const sessionUser = await getSessionUser();
  if (sessionUser) {
    redirect("/dashboard");
  }

  return (
    <>
      <RegisterForm />
      <p className="mt-[-5rem] pb-8 text-center text-sm">
        Already have an account? <Link className="link link-primary" href="/login">Login</Link>
      </p>
    </>
  );
}

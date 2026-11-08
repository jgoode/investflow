import { redirect } from "next/navigation";

import { getSessionUser } from "@/lib/auth-session";

import { MegaMenu } from "./mega-menu";

export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const sessionUser = await getSessionUser();
  if (!sessionUser) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-base-100">
      <MegaMenu username={sessionUser.username} />
      <main>{children}</main>
    </div>
  );
}

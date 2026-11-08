import { cookies } from "next/headers";

import { apiUrl } from "@/lib/api";

type SessionUser = {
  id: number;
  username: string;
  display_name: string | null;
  is_active: boolean;
  session_epoch: number;
};

export async function getSessionUser(): Promise<SessionUser | null> {
  const session = (await cookies()).get("investflow_session")?.value;
  if (!session) {
    return null;
  }

  const response = await fetch(apiUrl("/api/auth/me"), {
    method: "GET",
    headers: {
      Cookie: `investflow_session=${session}`,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }

  const payload = (await response.json()) as { user: SessionUser };
  return payload.user;
}

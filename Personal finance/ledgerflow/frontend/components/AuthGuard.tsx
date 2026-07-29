"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import NavBar from "@/components/NavBar";
import { getMe } from "@/lib/api";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authed, setAuthed] = useState<boolean | null>(null);

  // The redirect decision is made inside the resolved callback (using the
  // pathname captured at the time this effect ran), not in a separate effect
  // reading `authed` — otherwise a stale `authed` value from before a
  // successful login/register can bounce straight back to /login before the
  // fresh check lands.
  useEffect(() => {
    let cancelled = false;
    getMe()
      .then(() => {
        if (cancelled) return;
        setAuthed(true);
        if (pathname === "/login") router.replace("/");
      })
      .catch(() => {
        if (cancelled) return;
        setAuthed(false);
        if (pathname !== "/login") router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  // The server enforces the idle session timeout on every request, but an
  // idle tab makes none — so poll periodically to notice a timed-out
  // session and bounce to /login promptly instead of only on the next
  // click.
  useEffect(() => {
    if (pathname === "/login" || !authed) return;

    const interval = setInterval(() => {
      getMe().catch(() => {
        setAuthed(false);
        router.replace("/login");
      });
    }, 60_000);

    return () => clearInterval(interval);
  }, [pathname, authed, router]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (!authed) {
    return null;
  }

  return (
    <>
      <NavBar />
      {children}
    </>
  );
}

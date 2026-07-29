"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { logout } from "@/lib/api";

const PRIMARY_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/accounts", label: "Accounts" },
  { href: "/transactions", label: "Transactions" },
];

const PLANNING_LINKS = [
  { href: "/budgets", label: "Budgets" },
  { href: "/income", label: "Income" },
  { href: "/assets", label: "Assets" },
  { href: "/reports/pnl", label: "P&L Statement" },
];

const SETTINGS_LINK = { href: "/settings", label: "Settings" };

const ALL_LINKS = [...PRIMARY_LINKS, ...PLANNING_LINKS, SETTINGS_LINK];

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [planningOpen, setPlanningOpen] = useState(false);
  const planningRef = useRef<HTMLDivElement>(null);

  const inPlanningSection = PLANNING_LINKS.some((link) => link.href === pathname);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (planningRef.current && !planningRef.current.contains(e.target as Node)) {
        setPlanningOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleLogout() {
    setOpen(false);
    await logout().catch(() => {});
    router.replace("/login");
  }

  return (
    <nav className="nav">
      <div className="navInner">
        <Link href="/" className="brand" onClick={() => setOpen(false)}>
          LedgerFlow
        </Link>

        <div className="navLinks">
          {PRIMARY_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={pathname === link.href ? "active" : ""}
            >
              {link.label}
            </Link>
          ))}

          <div className="navDropdown" ref={planningRef}>
            <button
              type="button"
              className={inPlanningSection ? "active" : ""}
              aria-expanded={planningOpen}
              onClick={() => setPlanningOpen((v) => !v)}
            >
              Planning ▾
            </button>
            {planningOpen && (
              <div className="navDropdownMenu">
                {PLANNING_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={pathname === link.href ? "active" : ""}
                    onClick={() => setPlanningOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            )}
          </div>

          <Link
            href={SETTINGS_LINK.href}
            className={pathname === SETTINGS_LINK.href ? "active" : ""}
          >
            {SETTINGS_LINK.label}
          </Link>

          <button type="button" className="btn btnSecondary btnSmall" onClick={handleLogout}>
            Log out
          </button>
        </div>

        <button
          type="button"
          className="menuButton"
          aria-label="Toggle menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "✕" : "☰"}
        </button>
      </div>

      {open && (
        <div className="mobileMenu">
          {ALL_LINKS.map((link) => (
            <Link key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </Link>
          ))}
          <button type="button" className="btn btnSecondary btnSmall" onClick={handleLogout}>
            Log out
          </button>
        </div>
      )}
    </nav>
  );
}

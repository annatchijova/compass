"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass } from "lucide-react";
import { CompassLogo, CompassWordmark } from "@/components/CompassLogo";

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="nav-glass">
      <div className="nav-inner">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
          <Link
            href="/"
            aria-label="COMPASS home"
            className="inline-flex flex-shrink-0 items-center gap-2.5"
          >
            <CompassLogo />
            <CompassWordmark />
          </Link>

          <nav className="flex items-center gap-1" aria-label="Primary">
            <Link
              href="/#how"
              className="rounded-full px-3 py-1.5 text-[13px] font-semibold text-ink-500 transition hover:bg-ink-900/5 hover:text-ink-900"
            >
              How it works
            </Link>
            <Link
              href="/compass"
              className={`btn-primary shadow-soft inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-bold ${
                pathname.startsWith("/compass") ? "shadow-glow" : ""
              }`}
            >
              <Compass className="h-4 w-4" />
              Open dashboard
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}

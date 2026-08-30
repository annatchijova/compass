"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Route } from "lucide-react";
import { CompassLogo, CompassWordmark } from "@/components/CompassLogo";
import { LanguageToggle } from "@/components/LanguageToggle";
import { useI18n } from "@/lib/i18n";

export function Navbar() {
  const pathname = usePathname();
  const { t } = useI18n();

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

          <nav className="flex items-center gap-2" aria-label="Primary">
            <Link
              href="/#how"
              className="hidden rounded-full px-3 py-1.5 text-[13px] font-semibold text-ink-500 transition hover:bg-ink-900/5 hover:text-ink-900 sm:inline-block"
            >
              {t("nav.how")}
            </Link>
            <Link
              href="/trajectories"
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold transition ${
                pathname.startsWith("/trajectories")
                  ? "bg-ink-900/5 text-ink-900"
                  : "text-ink-500 hover:bg-ink-900/5 hover:text-ink-900"
              }`}
            >
              <Route className="h-4 w-4" />
              <span className="hidden sm:inline">{t("nav.trajectories")}</span>
            </Link>
            <LanguageToggle />
            <Link
              href="/compass"
              className={`btn-primary shadow-soft inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-bold ${
                pathname.startsWith("/compass") ? "shadow-glow" : ""
              }`}
            >
              <Compass className="h-4 w-4" />
              <span className="hidden sm:inline">{t("nav.dashboard")}</span>
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}

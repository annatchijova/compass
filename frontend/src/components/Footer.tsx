import { ShieldCheck } from "lucide-react";

export function Footer() {
  return (
    <footer className="mx-auto mt-10 flex max-w-7xl flex-wrap items-center justify-between gap-3 border-t border-ink-900/5 px-4 py-6 text-[12px] text-ink-400">
      <span>© 2026 COMPASS · No claim without sealed evidence</span>
      <span className="inline-flex items-center gap-4">
        <span className="inline-flex items-center gap-1.5 text-ink-500">
          <ShieldCheck className="h-3.5 w-3.5 text-brand-indigo" />
          Deterministic engine · Hash-chained ledger
        </span>
      </span>
    </footer>
  );
}

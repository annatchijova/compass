"use client";

import type { FlaskConical } from "lucide-react";
import { useI18n } from "@/lib/i18n";

/* Shared dashboard primitives (VELO look). Extracted from the compass page so
   panels living in their own files render inside the same card chrome. */

// Small rounded ghost/pill chips (VELO look). Clicking a chip only FILLS the
// target input via onPick — the user still clicks the real action button.
export function ExampleChips({
  hint,
  examples,
  onPick,
}: {
  hint: string;
  examples: string[];
  onPick: (value: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wide text-ink-400">
          {t("examples.label")}
        </span>
        <span className="text-[11px] text-ink-400">{hint}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {examples.map((ex, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onPick(ex)}
            title={ex}
            className="btn-ghost max-w-full truncate rounded-full px-3 py-1.5 text-left text-[11.5px] font-semibold"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  icon: Icon,
  children,
}: {
  title: string;
  subtitle?: string;
  icon: typeof FlaskConical;
  children: React.ReactNode;
}) {
  return (
    <div className="animate-fade-up card-solid shadow-soft rounded-3xl p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-indigo/10 text-brand-deep">
          <Icon className="h-4.5 w-4.5" />
        </span>
        <div>
          <h2 className="font-display text-[17px] font-extrabold tracking-tight text-ink-900">
            {title}
          </h2>
          {subtitle && <p className="text-[12px] leading-snug text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-ink-900/15 bg-ink-900/[0.02] p-5 text-center text-[12.5px] text-ink-500">
      {children}
    </div>
  );
}

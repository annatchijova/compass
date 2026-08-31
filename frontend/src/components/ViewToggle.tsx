"use client";

import { Leaf, LayoutGrid } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { ViewMode } from "@/lib/viewMode";

/**
 * Calm ↔ Full view toggle. Calm is the default. Small, clear, no alarm color —
 * matches the LanguageToggle chrome so it reads as a quiet preference control.
 */
export function ViewToggle({
  mode,
  onChange,
}: {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
}) {
  const { t } = useI18n();
  const options: { value: ViewMode; label: string; icon: typeof Leaf }[] = [
    { value: "calm", label: t("calm.view.calm"), icon: Leaf },
    { value: "full", label: t("calm.view.full"), icon: LayoutGrid },
  ];
  return (
    <div
      className="flex items-center rounded-full border border-ink-900/10 bg-white p-0.5"
      role="group"
      aria-label={t("calm.view.aria")}
    >
      {options.map((o) => {
        const Icon = o.icon;
        const active = mode === o.value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            aria-pressed={active}
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold transition ${
              active
                ? "bg-brand-mustard text-ink-900 shadow-sm"
                : "text-ink-400 hover:text-ink-700"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

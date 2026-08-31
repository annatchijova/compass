"use client";

import { useI18n } from "@/lib/i18n";

export function LanguageToggle() {
  const { lang, setLang } = useI18n();
  return (
    <div
      className="flex items-center rounded-full border border-ink-900/10 bg-white p-0.5"
      role="group"
      aria-label="Language"
    >
      {(["en", "es"] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase transition ${
            lang === l
              ? "bg-brand-mustard text-ink-900 shadow-sm"
              : "text-ink-400 hover:text-ink-700"
          }`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

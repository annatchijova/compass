"use client";

import type { FitStatus } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

// Fit chip colors mirror the hypothesis StatusChip palette:
//   met      -> strong indigo (like corroborada)
//   supported-> cyan          (like activa)
//   open     -> muted/grey    (like latente)
//   against  -> amber         (like debilitada)
//   discarded-> grey + strike (like descartada)
const FIT_STYLE: Record<
  FitStatus,
  { bg: string; text: string; dot: string; strike?: boolean }
> = {
  met: { bg: "bg-status-corroboradaBg", text: "text-status-corroborada", dot: "#4F46E5" },
  supported: { bg: "bg-status-activaBg", text: "text-status-activa", dot: "#0891B2" },
  open: { bg: "bg-status-latenteBg", text: "text-status-latente", dot: "#5B6B84" },
  against: { bg: "bg-status-debilitadaBg", text: "text-status-debilitada", dot: "#B45309" },
  discarded: {
    bg: "bg-status-descartadaBg",
    text: "text-status-descartada",
    dot: "#64748B",
    strike: true,
  },
};

export function fitColor(fit: FitStatus): string {
  return (FIT_STYLE[fit] ?? FIT_STYLE.open).dot;
}

export function fitIsStruck(fit: FitStatus): boolean {
  return Boolean((FIT_STYLE[fit] ?? FIT_STYLE.open).strike);
}

export function FitChip({ fit }: { fit: FitStatus }) {
  const { t } = useI18n();
  const s = FIT_STYLE[fit] ?? FIT_STYLE.open;
  const label = t(`fit.${fit}` as never) || fit;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${s.bg} ${s.text}`}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.dot }} />
      {label}
    </span>
  );
}

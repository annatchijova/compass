import type { HypothesisStatus } from "@/lib/types";

// Color per hypothesis status. UI chrome only — never a computed value.
const STATUS_STYLE: Record<
  HypothesisStatus,
  { label: string; bg: string; text: string; dot: string; strike?: boolean }
> = {
  corroborada: {
    label: "corroborada",
    bg: "bg-status-corroboradaBg",
    text: "text-status-corroborada",
    dot: "#4F46E5",
  },
  activa: {
    label: "activa",
    bg: "bg-status-activaBg",
    text: "text-status-activa",
    dot: "#0891B2",
  },
  latente: {
    label: "latente",
    bg: "bg-status-latenteBg",
    text: "text-status-latente",
    dot: "#5B6B84",
  },
  debilitada: {
    label: "debilitada",
    bg: "bg-status-debilitadaBg",
    text: "text-status-debilitada",
    dot: "#B45309",
  },
  descartada: {
    label: "descartada",
    bg: "bg-status-descartadaBg",
    text: "text-status-descartada",
    dot: "#64748B",
    strike: true,
  },
};

export function statusColor(status: HypothesisStatus): string {
  return (STATUS_STYLE[status] ?? STATUS_STYLE.latente).dot;
}

export function statusIsStruck(status: HypothesisStatus): boolean {
  return Boolean((STATUS_STYLE[status] ?? STATUS_STYLE.latente).strike);
}

export function StatusChip({ status }: { status: HypothesisStatus }) {
  const s = STATUS_STYLE[status] ?? STATUS_STYLE.latente;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${s.bg} ${s.text}`}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.dot }} />
      {s.label}
    </span>
  );
}

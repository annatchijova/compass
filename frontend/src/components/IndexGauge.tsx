"use client";

import { useEffect, useState } from "react";
import { clampIndex } from "@/lib/utils";
import { statusColor } from "@/components/StatusChip";
import { useI18n } from "@/lib/i18n";
import type { HypothesisStatus } from "@/lib/types";

/**
 * COMPASS confidence-index gauge. The index is an INTEGER 0–1000 meaning
 * "accumulation of evidence under versioned rules". It is emphatically NOT a
 * probability or percentage, so this gauge renders the raw integer out of
 * 1000 — never a % — and carries a caption to that effect.
 *
 * Adapted from VELO's VerdictGauge (same ring geometry / animation).
 */
export function IndexGauge({
  index,
  status,
}: {
  index: number | null;
  status: HypothesisStatus;
}) {
  const { t } = useI18n();
  const value = clampIndex(index); // 0–1000
  const [progress, setProgress] = useState(0);
  const color = statusColor(status);
  const R = 80;
  const CIRC = 2 * Math.PI * R;

  useEffect(() => {
    const t = setTimeout(() => setProgress(value), 60);
    return () => clearTimeout(t);
  }, [value]);

  const pct = Math.min(Math.max(progress / 1000, 0), 1);
  const isNull = index == null;

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-[168px] w-[168px]">
        <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90">
          <circle
            cx="100"
            cy="100"
            r={R}
            fill="none"
            stroke="rgba(21,25,29,0.07)"
            strokeWidth="14"
          />
          {!isNull && (
            <circle
              cx="100"
              cy="100"
              r={R}
              fill="none"
              stroke={color}
              strokeWidth="14"
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={CIRC * (1 - pct)}
              style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.23,1,0.32,1)" }}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {isNull ? (
            <span className="font-display text-[26px] font-extrabold leading-none tracking-tight text-ink-400">
              —
            </span>
          ) : (
            <span
              className="font-display text-[34px] font-extrabold leading-none tracking-tight"
              style={{ color }}
            >
              {value}
              <span className="text-[14px] font-bold text-ink-400"> {t("gauge.unit")}</span>
            </span>
          )}
          <span className="mt-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-ink-400">
            {t("gauge.label")}
          </span>
        </div>
      </div>
      <p className="mt-2 max-w-[240px] text-center text-[11px] leading-relaxed text-ink-500">
        {t("gauge.caption")}
      </p>
    </div>
  );
}

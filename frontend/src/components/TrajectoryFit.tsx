"use client";

import { Target, Compass } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { CapabilitySuggestions } from "@/components/CapabilitySuggestions";
import { clampIndex } from "@/lib/utils";
import { localizeSeed } from "@/lib/seedI18n";
import type {
  FitState,
  TrajectoryFitResponse,
  TrajectoryRequirement,
} from "@/lib/types";

/**
 * Vocational fit for one trajectory.
 *
 * Two rules this component exists to honour, both from the design doc (§5/§7):
 *
 *  1. **No destiny percentage.** The backend answers in COUNTS per fit state,
 *     and so does this view. There is deliberately no ratio, no "72% match",
 *     no progress bar over `met / total` — a fraction of requirements met is
 *     exactly the flattering number the project refuses to invent.
 *  2. **Read-only over sealed state.** A fit is a projection over hypotheses
 *     that were already sealed by the deterministic engine. Rendering it
 *     moves no index and appends nothing to the chain.
 *
 * Each fit state maps 1:1 from a hypothesis status, so it reuses the same
 * palette the rest of the dashboard uses for that status.
 */

const FIT_ORDER: FitState[] = ["met", "supported", "open", "against", "discarded"];

// Mirrors the backend's _RESOLVED set: these no longer discriminate, so
// there is nothing left to go and test for them.
const RESOLVED: FitState[] = ["met", "against", "discarded"];

// met←corroborada, supported←activa, open←latente, against←debilitada,
// discarded←descartada. UI chrome only — never a computed value.
const FIT_STYLE: Record<FitState, { bg: string; text: string; dot: string }> = {
  met: { bg: "bg-status-corroboradaBg", text: "text-status-corroborada", dot: "#4F46E5" },
  supported: { bg: "bg-status-activaBg", text: "text-status-activa", dot: "#0891B2" },
  open: { bg: "bg-status-latenteBg", text: "text-status-latente", dot: "#5B6B84" },
  against: { bg: "bg-status-debilitadaBg", text: "text-status-debilitada", dot: "#B45309" },
  discarded: { bg: "bg-status-descartadaBg", text: "text-status-descartada", dot: "#64748B" },
};

export function FitChip({ fit }: { fit: FitState }) {
  const { t } = useI18n();
  const s = FIT_STYLE[fit] ?? FIT_STYLE.open;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${s.bg} ${s.text}`}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.dot }} />
      {t(`fit.${fit}` as never) || fit}
    </span>
  );
}

/** Counts per state — five integers side by side, never combined into one. */
function FitSummary({ summary }: { summary: TrajectoryFitResponse["summary"] }) {
  const { t } = useI18n();
  return (
    <div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        {FIT_ORDER.map((state) => {
          const s = FIT_STYLE[state];
          const n = summary[state] ?? 0;
          return (
            <div
              key={state}
              className={`rounded-2xl px-3 py-2.5 ${n > 0 ? s.bg : "bg-ink-900/[0.02]"}`}
            >
              <p
                className={`font-display text-[22px] font-extrabold leading-none tracking-tight ${
                  n > 0 ? s.text : "text-ink-400"
                }`}
              >
                {n}
              </p>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-ink-500">
                {t(`fit.${state}` as never) || state}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[11.5px] text-ink-500">
        {summary.total} {t("fit.total")} · {t("traj.noPercentage")}
      </p>
    </div>
  );
}

function RequirementRow({
  req,
  onChanged,
}: {
  req: TrajectoryRequirement;
  onChanged: () => void;
}) {
  const { t, lang } = useI18n();
  return (
    <div className="card-solid rounded-2xl p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Label and hypothesis statement are user-authored; seed fixtures are
            localized for display only. */}
        <p className="min-w-0 flex-1 text-[13px] font-bold text-ink-900">
          {localizeSeed(req.label, lang)}
        </p>
        <FitChip fit={req.fit} />
      </div>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-600">
        {localizeSeed(req.hypothesis_statement, lang)}
      </p>
      <div className="mt-2 flex items-center gap-2 text-[11px] text-ink-400">
        <span className="font-mono">
          {t("traj.req.backedBy", { id: String(req.hypothesis_id) })}
        </span>
        <span aria-hidden>·</span>
        {/* The index is an integer out of 1000 — never rendered as a % */}
        <span className="font-mono">
          {req.index == null ? "—" : `${clampIndex(req.index)}/1000`}
        </span>
      </div>
      {!RESOLVED.includes(req.fit) && (
        <CapabilitySuggestions
          hypothesisId={req.hypothesis_id}
          onPreregistered={onChanged}
        />
      )}
    </div>
  );
}

export function TrajectoryFit({
  fit,
  onChanged,
}: {
  fit: TrajectoryFitResponse;
  onChanged: () => void;
}) {
  const { t, lang } = useI18n();
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <Compass className="h-4 w-4 shrink-0 text-brand-indigo" />
          <h3 className="font-display text-[15px] font-extrabold tracking-tight text-ink-900">
            {localizeSeed(fit.trajectory.name, lang)}
          </h3>
        </div>
        {fit.trajectory.description && (
          <p className="mt-1 text-[12.5px] leading-relaxed text-ink-600">
            {localizeSeed(fit.trajectory.description, lang)}
          </p>
        )}
      </div>

      <FitSummary summary={fit.summary} />

      <div>
        <p className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
          <Target className="h-3.5 w-3.5" />
          {t("traj.requirements")}
        </p>
        {fit.requirements.length > 0 ? (
          <div className="space-y-2">
            {fit.requirements.map((r) => (
              <RequirementRow
                key={r.requirement_id}
                req={r}
                onChanged={onChanged}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-ink-900/15 bg-ink-900/[0.02] p-4 text-center text-[12.5px] text-ink-500">
            {t("traj.req.empty")}
          </div>
        )}
      </div>
    </div>
  );
}

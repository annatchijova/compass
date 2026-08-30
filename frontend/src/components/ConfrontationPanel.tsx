"use client";

import { AlertCircle, Scale } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/Panel";
import type { Confrontation, ConfrontationsResponse } from "@/lib/types";

/**
 * Self-perception vs. data (design doc §5) — the most powerful moment in the
 * concept and the most dangerous.
 *
 * Every sentence here comes from a FIXED TEMPLATE filled with counts the
 * deterministic engine produced. No model decides whether a discrepancy
 * exists and no model phrases it: under narrative pressure a model can turn
 * "these two records disagree" into "here is who you are", which is exactly
 * what §5 forbids.
 *
 * The panel shows the policy it was judged under, and says out loud that the
 * thresholds are PROVISIONAL (§9), so a reader can argue with the rule
 * rather than with the conclusion.
 */
export function ConfrontationPanel({
  data,
  error,
}: {
  data: ConfrontationsResponse | null;
  error?: string | null;
}) {
  const { t } = useI18n();
  if (!data && !error) return null;

  return (
    <Panel title={t("conf.title")} subtitle={t("conf.subtitle")} icon={Scale}>
      {error && (
        <p className="flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {error}
        </p>
      )}

      {data && data.confrontations.length === 0 && (
        <p className="text-[12.5px] leading-relaxed text-ink-600">
          {t("conf.none")}
        </p>
      )}

      {data?.confrontations.map((c) => (
        <Discrepancy key={c.hypothesis_id} c={c} />
      ))}

      {data && data.held_back > 0 && (
        <p className="mt-2 text-[11.5px] text-ink-500">
          {t("conf.heldBack", { n: data.held_back })}
        </p>
      )}

      {data && (
        <p className="mt-3 border-t border-ink-900/5 pt-2 text-[11px] leading-relaxed text-ink-400">
          {t("conf.policy", {
            version: data.policy.policy_version,
            threshold: data.policy.index_threshold,
            types: data.policy.min_distinct_types,
          })}
        </p>
      )}
    </Panel>
  );
}

function Discrepancy({ c }: { c: Confrontation }) {
  const { t } = useI18n();
  // The only variable part is the counts. The wording is ours, not a model's.
  const sentence =
    c.kind === "record_exceeds_self"
      ? t("conf.record_exceeds_self", {
          selfContra: c.self_contradicts,
          recordPro: c.record_supports,
        })
      : t("conf.self_exceeds_record", {
          selfPro: c.self_supports,
          recordContra: c.record_contradicts,
        });

  return (
    <div className="rounded-2xl bg-status-activaBg p-3.5">
      {/* The hypothesis statement is the person's own words, rendered as-is */}
      <p className="text-[13px] font-bold text-ink-900">{c.hypothesis_statement}</p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-700">{sentence}</p>
      <p className="mt-2 text-[11.5px] leading-relaxed text-ink-500">
        {t("conf.notAVerdict")}
      </p>
      <p className="mt-2 font-mono text-[10.5px] text-ink-400">
        hypothesis #{c.hypothesis_id} · {c.index ?? "—"}/1000 ·{" "}
        {t("conf.evidenceTypes", { n: c.distinct_types })}
      </p>
    </div>
  );
}

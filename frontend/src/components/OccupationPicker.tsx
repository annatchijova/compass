"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Briefcase, RefreshCw, Check } from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Empty } from "@/components/Panel";
import type {
  OnetOccupationSummary,
  OnetOccupationDetail,
} from "@/lib/types";

/**
 * Start a trajectory from a real O*NET occupation. Selecting one shows its
 * evidence-based required capabilities (rendered as-is, already in the
 * requested language); adopting builds a trajectory whose requirements all
 * start "open". The O*NET attribution (CC BY 4.0) is shown wherever this data
 * appears — it must never be omitted.
 */
export function OccupationPicker({
  onAdopted,
}: {
  /** Called with the new trajectory id so the parent can refresh + select it. */
  onAdopted: (trajectoryId: string) => void | Promise<void>;
}) {
  const { t, lang } = useI18n();
  const [occupations, setOccupations] = useState<OnetOccupationSummary[] | null>(null);
  const [attribution, setAttribution] = useState<string>("");
  const [code, setCode] = useState<string>("");
  const [detail, setDetail] = useState<OnetOccupationDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "list" | "detail" | "adopt">("list");

  const loadList = useCallback(async () => {
    setBusy("list");
    setErr(null);
    try {
      const res = await api.getOccupations(lang);
      setOccupations(res.occupations);
      setAttribution(res.attribution);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.onet"));
    } finally {
      setBusy(null);
    }
  }, [lang, t]);

  // Reload the list (and any open detail) when the UI language changes.
  useEffect(() => {
    void loadList();
    setCode("");
    setDetail(null);
  }, [loadList]);

  const onPick = async (nextCode: string) => {
    setCode(nextCode);
    setDetail(null);
    setErr(null);
    if (!nextCode) return;
    setBusy("detail");
    try {
      const res = await api.getOccupation(nextCode, lang);
      setDetail(res);
      if (res.attribution) setAttribution(res.attribution);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.onetDetail"));
    } finally {
      setBusy(null);
    }
  };

  const adopt = async () => {
    if (!code) return;
    setBusy("adopt");
    setErr(null);
    try {
      const res = await api.adoptOccupation(code, lang);
      // Reuse the parent's refetch/select flow so the new fit shows.
      await onAdopted(String(res.trajectory_id));
      // Reset the picker after a successful adoption.
      setCode("");
      setDetail(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.onetAdopt"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mt-4 border-t border-ink-900/5 pt-4">
      <p className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        <Briefcase className="h-3.5 w-3.5" />
        {t("onet.start")}
      </p>
      <p className="mb-3 text-[12px] leading-relaxed text-ink-500">{t("onet.caption")}</p>

      {busy === "list" && !occupations ? (
        <p className="flex items-center gap-1.5 text-[12px] text-ink-400">
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          {t("onet.loading")}
        </p>
      ) : occupations && occupations.length > 0 ? (
        <label className="block">
          <span className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("onet.pick")}
          </span>
          <select
            value={code}
            onChange={(e) => void onPick(e.target.value)}
            className="field-input w-full"
          >
            <option value="">{t("onet.pickPlaceholder")}</option>
            {occupations.map((o) => (
              <option key={o.code} value={o.code}>
                {o.title} · {o.riasec} ({o.requirement_count})
              </option>
            ))}
          </select>
        </label>
      ) : (
        occupations && <Empty>{t("onet.empty")}</Empty>
      )}

      {/* Selected occupation detail */}
      {busy === "detail" && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-ink-400">
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          {t("onet.loading")}
        </p>
      )}

      {detail && (
        <div className="mt-3 rounded-2xl bg-ink-900/[0.02] p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13.5px] font-bold text-ink-900">{detail.title}</span>
            <span
              className="rounded-full bg-brand-indigo/10 px-2 py-0.5 font-mono text-[11px] font-bold tracking-wide text-brand-deep"
              title={t("onet.riasecLabel")}
            >
              {detail.riasec}
            </span>
          </div>

          <p className="mt-2 text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
            {t("onet.reqCount", { n: detail.requirements.length })}
          </p>
          {/* Requirement statements are API-authored in the requested language
              — rendered as-is, never translated client-side. */}
          <ul className="mt-1.5 space-y-1">
            {detail.requirements.map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-1.5 text-[12.5px] leading-relaxed text-ink-700"
              >
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-indigo/50" />
                {r}
              </li>
            ))}
          </ul>

          <button
            onClick={() => void adopt()}
            disabled={busy === "adopt"}
            className="btn-primary shadow-soft mt-3 inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
          >
            {busy === "adopt" ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                {t("onet.adopting")}
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                {t("onet.adopt")}
              </>
            )}
          </button>
        </div>
      )}

      {err && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {/* O*NET attribution — CC BY 4.0 requirement, always shown. */}
      {attribution && (
        <p className="mt-3 text-[10.5px] leading-relaxed text-ink-400">{attribution}</p>
      )}
    </div>
  );
}

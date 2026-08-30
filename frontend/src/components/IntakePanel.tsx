"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ClipboardList,
  X,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  Brain,
  Compass as CompassIcon,
  FlaskConical,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type {
  Instrument,
  IntakeItem,
  IntakeProposal,
} from "@/lib/types";
import { Panel, Empty } from "@/components/Panel";

type Step = "pick" | "questionnaire" | "results";

/**
 * Vocational intake (Big Five + RIASEC). A short questionnaire that SEEDS
 * candidate hypotheses to test — never a verdict. Scores are shown as integer
 * raw/max counts, never a percentage or percentile. Registering a proposal
 * creates a PENDING hypothesis (validated=false).
 */
export function IntakePanel({ onRegistered }: { onRegistered?: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <Panel
      title={t("intake.panel.title")}
      subtitle={t("intake.panel.subtitle")}
      icon={ClipboardList}
    >
      <p className="mb-3 text-[11.5px] italic leading-relaxed text-ink-400">
        {t("intake.caption")}
      </p>
      <button
        onClick={() => setOpen(true)}
        className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        <ClipboardList className="h-4 w-4" />
        {t("intake.open")}
      </button>

      {open && (
        <IntakeModal
          onClose={() => setOpen(false)}
          onRegistered={onRegistered}
        />
      )}
    </Panel>
  );
}

function IntakeModal({
  onClose,
  onRegistered,
}: {
  onClose: () => void;
  onRegistered?: () => void;
}) {
  const { t, lang } = useI18n();
  const [step, setStep] = useState<Step>("pick");
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [assessmentId, setAssessmentId] = useState<number | string | null>(null);
  const [proposals, setProposals] = useState<IntakeProposal[]>([]);
  const [note, setNote] = useState<string>("");
  const [registered, setRegistered] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const reset = useCallback(() => {
    setStep("pick");
    setInstrument(null);
    setItems([]);
    setAnswers({});
    setAssessmentId(null);
    setProposals([]);
    setNote("");
    setRegistered({});
    setErr(null);
  }, []);

  const startInstrument = async (inst: Instrument) => {
    setBusy(true);
    setErr(null);
    setInstrument(inst);
    try {
      const res = await api.getIntakeItems(inst, lang);
      setItems(res.items);
      setAnswers({});
      setStep("questionnaire");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("intake.err.items"));
      setInstrument(null);
    } finally {
      setBusy(false);
    }
  };

  const answered = Object.keys(answers).length;
  const allAnswered = items.length > 0 && answered === items.length;

  const finish = async () => {
    if (!instrument || !allAnswered) return;
    setBusy(true);
    setErr(null);
    try {
      const created = await api.createAssessment(instrument);
      const id = created.assessment_id;
      setAssessmentId(id);
      const responses = items.map((it) => ({
        item_code: it.code,
        value: answers[it.code],
      }));
      await api.submitResponses(id, responses);
      const res = await api.getIntakeProposals(id);
      setProposals(res.proposals);
      setNote(res.note ?? "");
      setStep("results");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("intake.err.submit"));
    } finally {
      setBusy(false);
    }
  };

  const register = async (dimension: string) => {
    if (assessmentId == null) return;
    setBusy(true);
    setErr(null);
    try {
      await api.registerIntakeProposal(assessmentId, dimension);
      setRegistered((prev) => ({ ...prev, [dimension]: true }));
      onRegistered?.();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("intake.err.register"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={t("intake.panel.title")}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="glass shadow-lift animate-fade-up my-8 w-full max-w-2xl rounded-3xl p-6">
        {/* Header */}
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl brand-gradient text-white">
              <ClipboardList className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-[10.5px] font-extrabold uppercase tracking-[0.1em] text-brand-deep">
                {t("intake.panel.title")}
              </p>
              <h2 className="font-display text-[18px] font-extrabold tracking-tight text-ink-900">
                {step === "pick" && t("intake.pick.title")}
                {step === "questionnaire" && t("intake.q.title")}
                {step === "results" && t("intake.results.title")}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label={t("intake.close")}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-400 transition hover:bg-ink-900/5 hover:text-ink-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Honest caption, always visible */}
        <p className="mb-4 rounded-2xl bg-brand-indigo/[0.06] px-3.5 py-2.5 text-[12px] italic leading-relaxed text-ink-600">
          {t("intake.caption")}
        </p>

        {err && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-status-debilitada/25 bg-status-debilitadaBg px-4 py-3 text-[13px] text-status-debilitada">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {err}
          </div>
        )}

        {/* Step: pick instrument */}
        {step === "pick" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <InstrumentCard
              icon={Brain}
              title={t("intake.pick.bigFive")}
              desc={t("intake.pick.bigFiveDesc")}
              disabled={busy}
              onClick={() => void startInstrument("big_five")}
            />
            <InstrumentCard
              icon={CompassIcon}
              title={t("intake.pick.riasec")}
              desc={t("intake.pick.riasecDesc")}
              disabled={busy}
              onClick={() => void startInstrument("riasec")}
            />
          </div>
        )}

        {/* Step: questionnaire */}
        {step === "questionnaire" && instrument && (
          <div>
            <div className="mb-3 flex items-center justify-between">
              <button
                onClick={reset}
                className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-bold"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                {t("intake.q.back")}
              </button>
              <span className="text-[12px] font-semibold text-ink-500">
                {t("intake.q.progress", { answered, total: items.length })}
              </span>
            </div>

            <div className="space-y-3">
              {items.map((it) => (
                <LikertRow
                  key={it.code}
                  instrument={instrument}
                  item={it}
                  value={answers[it.code]}
                  onChange={(v) =>
                    setAnswers((prev) => ({ ...prev, [it.code]: v }))
                  }
                />
              ))}
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => void finish()}
                disabled={busy || !allAnswered}
                className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
              >
                {busy ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                {t("intake.q.finish")}
              </button>
            </div>
          </div>
        )}

        {/* Step: results */}
        {step === "results" && (
          <div>
            {proposals.length === 0 ? (
              <Empty>{t("intake.results.title")}</Empty>
            ) : (
              <div className="space-y-2.5">
                {proposals.map((p) => (
                  <div key={p.dimension} className="card-solid rounded-2xl p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        {/* statement is API-authored (Spanish domain) — as-is */}
                        <p className="text-[13.5px] font-semibold leading-relaxed text-ink-900">
                          {p.statement}
                        </p>
                        {registered[p.dimension] && (
                          <p className="mt-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold text-status-corroborada">
                            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                            {t("intake.results.registered")}
                          </p>
                        )}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        {/* integer count, never a percentage */}
                        <span className="font-mono text-[13px] font-bold text-ink-700">
                          {p.raw} / {p.max}
                        </span>
                        {!registered[p.dimension] && (
                          <button
                            onClick={() => void register(p.dimension)}
                            disabled={busy}
                            className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
                          >
                            <FlaskConical className="h-3.5 w-3.5" />
                            {t("intake.results.register")}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* note is API-authored — rendered as-is */}
            {note && (
              <p className="mt-3 text-[12px] italic leading-relaxed text-ink-500">{note}</p>
            )}

            <div className="mt-4 flex justify-end">
              <button
                onClick={reset}
                className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
              >
                <RefreshCw className="h-4 w-4" />
                {t("intake.results.another")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InstrumentCard({
  icon: Icon,
  title,
  desc,
  disabled,
  onClick,
}: {
  icon: typeof Brain;
  title: string;
  desc: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="card-solid card-hover flex flex-col items-start gap-2 rounded-2xl p-4 text-left disabled:opacity-60"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-indigo/10 text-brand-deep">
        <Icon className="h-5 w-5" />
      </span>
      <p className="mt-1 font-display text-[16px] font-extrabold tracking-tight text-ink-900">
        {title}
      </p>
      <p className="text-[12px] leading-snug text-ink-500">{desc}</p>
    </button>
  );
}

function LikertRow({
  instrument,
  item,
  value,
  onChange,
}: {
  instrument: Instrument;
  item: IntakeItem;
  value: number | undefined;
  onChange: (v: number) => void;
}) {
  const { t } = useI18n();
  const low =
    instrument === "riasec" ? t("likert.riasec.low") : t("likert.bigFive.low");
  const high =
    instrument === "riasec" ? t("likert.riasec.high") : t("likert.bigFive.high");

  return (
    <div className="card-solid rounded-2xl p-3.5">
      {/* item text is API-authored in the requested language — as-is */}
      <p className="text-[13px] font-semibold leading-snug text-ink-900">{item.text}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <span className="hidden w-24 shrink-0 text-right text-[10px] leading-tight text-ink-400 sm:block">
          {low}
        </span>
        <div className="flex flex-1 items-center justify-between gap-1.5">
          {[1, 2, 3, 4, 5].map((v) => {
            const active = value === v;
            return (
              <button
                key={v}
                type="button"
                onClick={() => onChange(v)}
                aria-pressed={active}
                aria-label={`${item.text} — ${v}`}
                className={`flex h-9 w-9 items-center justify-center rounded-full border text-[12px] font-bold transition ${
                  active
                    ? "brand-gradient border-transparent text-white shadow-sm"
                    : "border-ink-900/12 bg-white text-ink-500 hover:border-brand-indigo/40 hover:text-ink-700"
                }`}
              >
                {v}
              </button>
            );
          })}
        </div>
        <span className="hidden w-24 shrink-0 text-left text-[10px] leading-tight text-ink-400 sm:block">
          {high}
        </span>
      </div>
      {/* mobile anchors */}
      <div className="mt-1.5 flex justify-between text-[10px] text-ink-400 sm:hidden">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  );
}

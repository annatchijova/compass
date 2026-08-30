"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ShieldCheck,
  ScrollText,
  CheckCircle2,
  RefreshCw,
  ChevronRight,
  ArrowRight,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n, nextStepSentence, narratorLanguage } from "@/lib/i18n";
import type {
  StateResponse,
  StateHypothesis,
  ChainResponse,
  Evidence,
  NextStep,
  ExperimentDraft,
  Prompt,
} from "@/lib/types";
import { shortHash, contentSnippet } from "@/lib/utils";
import { useAutoResize } from "@/lib/useAutoResize";
import { localizeSeed } from "@/lib/seedI18n";
import { CompassIdControl } from "@/components/CompassIdControl";
import { LanguageToggle } from "@/components/LanguageToggle";

/**
 * Calm mode — the DEFAULT view. Single focus, progressive disclosure, lots of
 * whitespace. Built for ADHD/autistic users (the primary audience): no motion
 * on entry, no alarm colors, no urgency, no gamification, no counting badges.
 *
 * Shows ONE focal thing — the deterministic next step — with a single inviting
 * action that depends on next_step.kind. Everything else is tucked behind the
 * quiet "Explore more" link at the bottom.
 */
export function CalmDashboard({
  state,
  chain,
  evidence,
  onUserChange,
  onValidate,
  validatingId,
  onExploreMore,
  onChanged,
}: {
  state: StateResponse | null;
  chain: ChainResponse | null;
  evidence: Evidence[] | null;
  onUserChange: () => void;
  onValidate: (id: number | string) => void;
  validatingId: number | string | null;
  onExploreMore: () => void;
  onChanged: () => void;
}) {
  const { t } = useI18n();
  const s = state?.state;
  const next = s?.next_step;

  const chainOk =
    chain != null &&
    chain.linkage_ok &&
    chain.integrity_ok &&
    chain.content_ok !== false;

  return (
    // No entrance animation in Calm mode: motion is a sensory cost for the
    // primary audience. (Global reduced-motion rules also disable it, but we
    // deliberately do not opt in here either.)
    <section className="mx-auto max-w-2xl px-4 pb-16 pt-8">
      {/* Minimal header: person, language, compass id, quiet chain dot */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="min-w-0 truncate font-display text-[clamp(22px,4vw,30px)] font-extrabold tracking-tight text-ink-900">
          {s?.person ?? t("dash.person.fallback")}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <LanguageToggle />
          <CompassIdControl onChange={onUserChange} />
        </div>
      </div>

      {/* Quiet chain indicator — not the big counts strip, no alarm color */}
      {chain && (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-400">
          <ScrollText className="h-3.5 w-3.5" />
          <span>
            {t("dash.chainPrefix")} {chainOk ? "✓" : "·"}
          </span>
          {state?.seal && (
            <span className="inline-flex items-center gap-1 font-mono text-ink-400">
              <ShieldCheck className="h-3 w-3" />
              {shortHash(state.seal, 8, 4)}
            </span>
          )}
        </div>
      )}

      {/* The hero: the single next step + one inviting action */}
      <div className="mt-10">
        {next ? (
          <NextStepHero
            next={next}
            hypotheses={s?.hypotheses ?? []}
            evidence={evidence}
            onValidate={onValidate}
            validatingId={validatingId}
            onChanged={onChanged}
          />
        ) : (
          <p className="text-center text-[15px] text-ink-500">{t("panel.chain.empty")}</p>
        )}
      </div>

      {/* Always-visible calm reassurance line */}
      <p className="mt-10 text-center text-[13px] italic text-ink-400">
        {t("calm.reassure")}
      </p>

      {/* One quiet progressive-disclosure link */}
      <div className="mt-8 flex justify-center">
        <button
          onClick={onExploreMore}
          className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-semibold text-ink-500 transition hover:bg-ink-900/5 hover:text-ink-700"
        >
          {t("calm.explore")}
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}

/* ─────────────────────────── the hero ─────────────────────────── */

function NextStepHero({
  next,
  hypotheses,
  evidence,
  onValidate,
  validatingId,
  onChanged,
}: {
  next: NextStep;
  hypotheses: StateHypothesis[];
  evidence: Evidence[] | null;
  onValidate: (id: number | string) => void;
  validatingId: number | string | null;
  onChanged: () => void;
}) {
  const { t, lang } = useI18n();
  const sentence = nextStepSentence(t, next);

  // When the step points at a specific hypothesis, show its statement so the
  // person knows WHICH one "#N" is — a bare id means nothing to them.
  const hypId = next.hypothesis_id as number | string | undefined;
  const referenced =
    hypId != null
      ? hypotheses.find((h) => String(h.id) === String(hypId))
      : undefined;

  return (
    <div className="glass shadow-soft rounded-3xl p-8 text-center">
      <p className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-brand-deep">
        {t("calm.next.eyebrow")}
      </p>
      <p className="mx-auto mt-4 max-w-xl text-[19px] font-semibold leading-relaxed text-ink-900">
        {sentence}
      </p>

      {/* The referenced hypothesis, in quotes — statement is API-authored;
          seed fixtures are localized for display only. */}
      {referenced && (
        <p className="mx-auto mt-3 max-w-xl text-[14px] italic leading-relaxed text-ink-500">
          “{localizeSeed(referenced.statement, lang)}”
        </p>
      )}

      <div className="mt-7">
        {next.kind === "validar_evidencia" && (
          <ValidateAction
            evidence={evidence}
            onValidate={onValidate}
            validatingId={validatingId}
          />
        )}
        {next.kind === "diseñar_experimento" && (
          <DesignAction hypothesisId={hypId} onPreregistered={onChanged} />
        )}
        {(next.kind === "completar_experimento" ||
          next.kind === "ejecutar_experimento") && <GuidanceCard sentence={sentence} />}
        {next.kind === "abstain" && <OnRamp onSaved={onChanged} />}
      </div>
    </div>
  );
}

/* ── validar_evidencia: inline pending-evidence mini-list ── */

function ValidateAction({
  evidence,
  onValidate,
  validatingId,
}: {
  evidence: Evidence[] | null;
  onValidate: (id: number | string) => void;
  validatingId: number | string | null;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const pending = (evidence ?? []).filter(
    (e) => e.deleted !== 1 && e.validated !== 1,
  );

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-6 py-3 text-[14px] font-bold"
      >
        {t("calm.action.validar_evidencia")}
        <ChevronRight className="h-4 w-4" />
      </button>
    );
  }

  return (
    <div className="text-left">
      {pending.length === 0 ? (
        <p className="text-center text-[13px] text-ink-500">{t("calm.empty.pending")}</p>
      ) : (
        <div className="space-y-2">
          {pending.map((e) => (
            <div
              key={e.id}
              className="card-solid flex items-center justify-between gap-3 rounded-2xl p-3.5"
            >
              <div className="min-w-0">
                {/* content is API-authored — rendered as-is */}
                <p className="truncate text-[12.5px] leading-snug text-ink-700">
                  {contentSnippet(e.content)}
                </p>
                <p className="mt-0.5 text-[11px] text-ink-400">{e.source}</p>
              </div>
              <button
                onClick={() => onValidate(e.id)}
                disabled={validatingId === e.id}
                className="btn-ghost inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
              >
                {validatingId === e.id ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                )}
                {t("btn.validate")}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── diseñar_experimento: design an experiment, edit the draft, preregister ── */

function DesignAction({
  hypothesisId,
  onPreregistered,
}: {
  hypothesisId?: number | string;
  onPreregistered: () => void;
}) {
  const { t, lang } = useI18n();
  // Editable working copy of the draft; null until designed. `note` is kept
  // separately for display only.
  const [draft, setDraft] = useState<ExperimentDraft | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<"design" | "preregister" | null>(null);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    if (hypothesisId == null) return;
    setBusy("design");
    setErr(null);
    try {
      const res = await api.designExperiment(hypothesisId, narratorLanguage(lang));
      setDraft(res.draft);
      setNote(res.note ?? null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.design"));
    } finally {
      setBusy(null);
    }
  };

  // The draft becomes a real preregistered experiment only here, with whatever
  // the person edited it into.
  const preregister = async () => {
    if (!draft || hypothesisId == null) return;
    setBusy("preregister");
    setErr(null);
    try {
      await api.postExperiment({ hypothesis_id: hypothesisId, ...draft });
      setDraft(null);
      setDone(true);
      onPreregistered();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.design"));
    } finally {
      setBusy(null);
    }
  };

  if (done) {
    return (
      <p className="rounded-2xl bg-brand-indigo/[0.06] p-4 text-[13.5px] leading-relaxed text-ink-700">
        {t("calm.design.preregistered")}
      </p>
    );
  }

  if (draft) {
    const set = (k: keyof ExperimentDraft, v: string) =>
      setDraft((d) => (d ? { ...d, [k]: v } : d));
    return (
      <div className="text-left">
        <DraftField
          label={t("calm.design.design")}
          value={draft.design}
          onChange={(v) => set("design", v)}
        />
        <DraftField
          label={t("calm.design.success")}
          value={draft.success_criterion}
          onChange={(v) => set("success_criterion", v)}
        />
        <DraftField
          label={t("calm.design.failure")}
          value={draft.failure_criterion}
          onChange={(v) => set("failure_criterion", v)}
        />
        {note && (
          <p className="mb-3 text-[11.5px] italic leading-relaxed text-ink-400">{note}</p>
        )}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => void preregister()}
            disabled={busy === "preregister"}
            className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
          >
            {busy === "preregister" && <RefreshCw className="h-4 w-4 animate-spin" />}
            {t("sugg.preregister")}
          </button>
          <button
            onClick={() => setDraft(null)}
            disabled={busy === "preregister"}
            className="btn-ghost rounded-full px-4 py-2.5 text-[13px] font-bold"
          >
            {t("sugg.discard")}
          </button>
        </div>
        {err && <p className="mt-2 text-[12px] text-ink-500">{err}</p>}
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => void run()}
        disabled={busy === "design" || hypothesisId == null}
        className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-6 py-3 text-[14px] font-bold"
      >
        {busy === "design" ? (
          <RefreshCw className="h-4 w-4 animate-spin" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        {t("calm.action.disenar_experimento")}
      </button>
      {err && <p className="mt-3 text-[12px] text-ink-500">{err}</p>}
    </div>
  );
}

function DraftField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  // Grow to fit the whole experiment text — no inner scrollbox, so the person
  // reads it all at a glance. min-height keeps a short draft comfortable.
  const ref = useAutoResize<HTMLTextAreaElement>(value);
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        {label}
      </span>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="field-input w-full resize-none overflow-hidden leading-relaxed"
        style={{ minHeight: "5.5rem" }}
      />
    </label>
  );
}

/* ── completar / ejecutar: calm guidance, no action ── */

function GuidanceCard({ sentence }: { sentence: string }) {
  const { t } = useI18n();
  return (
    <div className="rounded-2xl bg-ink-900/[0.02] p-5 text-left">
      <p className="text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        {t("calm.guide.title")}
      </p>
      <p className="mt-1.5 text-[14px] leading-relaxed text-ink-700">{sentence}</p>
    </div>
  );
}

/* ── abstain: the on-ramp, one gentle narrative question at a time ── */

function OnRamp({ onSaved }: { onSaved: () => void }) {
  const { t, lang } = useI18n();
  const [prompts, setPrompts] = useState<Prompt[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const loadPrompts = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await api.getPrompts(lang, "easy");
      setPrompts(res.prompts);
      setIdx(0);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.prompts"));
    } finally {
      setLoading(false);
    }
  }, [lang, t]);

  // Load once on mount and whenever the language changes.
  useEffect(() => {
    void loadPrompts();
  }, [loadPrompts]);

  const current = prompts && prompts.length > 0 ? prompts[idx % prompts.length] : null;

  const skip = () => {
    if (!prompts || prompts.length === 0) return;
    setIdx((i) => (i + 1) % prompts.length);
    setAnswer("");
  };

  const submit = async () => {
    if (!answer.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.extract(answer.trim(), narratorLanguage(lang));
      setSaved(true);
      setAnswer("");
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.extract"));
    } finally {
      setBusy(false);
    }
  };

  if (saved) {
    return (
      <p className="rounded-2xl bg-brand-indigo/[0.06] p-4 text-[13.5px] leading-relaxed text-ink-700">
        {t("calm.onramp.saved")}
      </p>
    );
  }

  if (loading) {
    return (
      <p className="flex items-center justify-center gap-1.5 text-[13px] text-ink-400">
        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
      </p>
    );
  }

  if (!current) {
    return <p className="text-[13px] text-ink-500">{t("calm.onramp.none")}</p>;
  }

  return (
    <div className="text-left">
      <p className="mb-3 text-center text-[13px] text-ink-500">{t("calm.onramp.intro")}</p>
      <div className="rounded-2xl bg-ink-900/[0.02] p-4">
        {/* prompt text is API-authored in the requested language — as-is */}
        <p className="text-[15px] font-semibold leading-relaxed text-ink-900">{current.text}</p>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={4}
          placeholder={t("calm.onramp.placeholder")}
          className="field-input mt-3 resize-y"
        />
        <div className="mt-3 flex items-center justify-between gap-3">
          <button
            onClick={skip}
            className="text-[12.5px] font-semibold text-ink-500 underline-offset-2 hover:underline"
          >
            {t("calm.onramp.skip")}
          </button>
          <button
            onClick={() => void submit()}
            disabled={busy || !answer.trim()}
            className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
          >
            {busy ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            {t("calm.onramp.submit")}
          </button>
        </div>
        {err && <p className="mt-2 text-[12px] text-ink-500">{err}</p>}
      </div>
    </div>
  );
}

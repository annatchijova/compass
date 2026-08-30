"use client";

import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  FlaskConical,
  ClipboardCheck,
  PlayCircle,
  PencilRuler,
  Pause,
  Sparkles,
  ScrollText,
  ClipboardList,
  CheckCircle2,
  Clock,
  Wand2,
  GitBranch,
  Plus,
  Link2,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n, nextStepSentence, narratorLanguage } from "@/lib/i18n";
import type {
  StateResponse,
  StateHypothesis,
  Hypothesis,
  Evidence,
  ChainResponse,
  ConfrontationsResponse,
  NextStep,
  NextStepKind,
  ExtractCandidate,
  NarrateResponse,
} from "@/lib/types";
import { shortHash, contentSnippet, formatDate } from "@/lib/utils";
import { localizeSeed } from "@/lib/seedI18n";
import { StatusChip, statusIsStruck } from "@/components/StatusChip";
import { IndexGauge } from "@/components/IndexGauge";
import { AuditChain } from "@/components/AuditChain";
import { CompassIdControl } from "@/components/CompassIdControl";
import { QuickTour } from "@/components/QuickTour";
import { Panel, Empty, ExampleChips } from "@/components/Panel";
import { TrajectoriesPanel } from "@/components/TrajectoriesPanel";
import { IntakePanel } from "@/components/IntakePanel";
import { ConfrontationPanel } from "@/components/ConfrontationPanel";
import { CalmDashboard } from "@/components/CalmDashboard";
import { ViewToggle } from "@/components/ViewToggle";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { getViewMode, setViewMode, type ViewMode } from "@/lib/viewMode";

const NEXT_STEP_ICON: Record<NextStepKind, typeof FlaskConical> = {
  completar_experimento: ClipboardCheck,
  ejecutar_experimento: PlayCircle,
  validar_evidencia: ClipboardCheck,
  "diseñar_experimento": PencilRuler,
  abstain: Pause,
};

export default function CompassDashboard() {
  const { t, lang } = useI18n();
  const [state, setState] = useState<StateResponse | null>(null);
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [chain, setChain] = useState<ChainResponse | null>(null);
  const [confrontations, setConfrontations] =
    useState<ConfrontationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // Bumped on every successful mutation. Panels that hold their own data
  // watch it, because not every write shows up in the SEALED state: a new
  // latent hypothesis is deliberately invisible there (design doc §3.2),
  // so nothing else would tell them to re-read.
  const [revision, setRevision] = useState(0);
  // View mode: Calm is the DEFAULT (accessible single-focus view). Start with
  // "calm" for SSR/first paint, then read the persisted choice in the browser.
  const [viewMode, setView] = useState<ViewMode>("calm");
  useEffect(() => {
    setView(getViewMode());
  }, []);
  const changeView = useCallback((m: ViewMode) => {
    setView(m);
    setViewMode(m);
  }, []);

  const fetchAll = useCallback(async () => {
    const [s, e, c, cf] = await Promise.all([
      api.getState(),
      api.getEvidence(),
      api.getChain(),
      api.getConfrontations(),
    ]);
    setState(s);
    setEvidence(e.evidence);
    setChain(c);
    setConfrontations(cf);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      await fetchAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("err.load"));
    } finally {
      setLoading(false);
    }
  }, [fetchAll, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const refetch = useCallback(async () => {
    try {
      await fetchAll();
      setRevision((r) => r + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("err.refetch"));
    }
  }, [fetchAll, t]);

  const onValidate = useCallback(
    async (id: number | string) => {
      setBusy(`validate-${id}`);
      try {
        await api.validateEvidence(id);
        await refetch();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("err.validate"));
      } finally {
        setBusy(null);
      }
    },
    [refetch, t],
  );

  // Switching the Compass ID loads a different isolated compass — show the
  // skeleton and do a full load so nothing from the previous compass lingers.
  const onUserChange = useCallback(() => {
    setLoading(true);
    setState(null);
    setEvidence(null);
    setChain(null);
    setConfrontations(null);
    void load();
  }, [load]);

  const onRecompute = useCallback(async () => {
    setBusy("recompute");
    try {
      await api.recompute();
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("err.recompute"));
    } finally {
      setBusy(null);
    }
  }, [refetch, t]);

  if (loading) return <DashboardSkeleton />;

  if (error && !state) {
    return <BackendUnreachable message={error} onRetry={() => void load()} />;
  }

  const s = state?.state;
  const visibleEvidence = (evidence ?? []).filter((e) => e.deleted !== 1);
  const unlinked = state?.coverage?.validated_unlinked ?? 0;
  // Which evidence row (if any) is mid-validation, for the calm mini-list.
  const validatingId: number | string | null =
    busy && busy.startsWith("validate-") ? busy.slice("validate-".length) : null;

  // ── Calm mode: the DEFAULT, single-focus view ──
  if (viewMode === "calm") {
    return (
      <DashboardErrorBoundary>
        <CalmDashboard
          state={state}
          chain={chain}
          evidence={evidence}
          onUserChange={onUserChange}
          onValidate={(id) => void onValidate(id)}
          validatingId={validatingId}
          onExploreMore={() => changeView("full")}
          onChanged={() => void refetch()}
        />
        {/* The Calm↔Full toggle lives in Calm's own header via a fixed corner
            control so the mode is always switchable without a counts strip. */}
        <div className="fixed right-4 top-[76px] z-30">
          <ViewToggle mode={viewMode} onChange={changeView} />
        </div>
      </DashboardErrorBoundary>
    );
  }

  return (
    <DashboardErrorBoundary>
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      {/* Header row */}
      <div className="animate-fade-up flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-ink-400">
            {t("dash.eyebrow")}
          </p>
          <h1 className="font-display text-[clamp(26px,4vw,38px)] font-extrabold tracking-tight text-ink-900">
            {s?.person ?? t("dash.person.fallback")}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12px] text-ink-500">
            <CompassIdControl onChange={onUserChange} />
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-900/5 px-2.5 py-1 font-mono text-[11px] text-ink-700">
              <ShieldCheck className="h-3.5 w-3.5 text-brand-indigo" />
              {t("dash.seal")} {shortHash(state?.seal, 10, 6)}
            </span>
            {chain && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  chain.linkage_ok &&
                  chain.integrity_ok &&
                  chain.content_ok !== false
                    ? "bg-status-corroboradaBg text-status-corroborada"
                    : "bg-status-debilitadaBg text-status-debilitada"
                }`}
              >
                <ScrollText className="h-3.5 w-3.5" />
                {t("dash.chainPrefix")} {t("dash.chain.linkage")}{" "}
                {chain.linkage_ok ? "✓" : "✗"} {t("dash.chain.integrity")}{" "}
                {chain.integrity_ok ? "✓" : "✗"}
                {chain.content_ok !== undefined && (
                  <>
                    {" "}
                    {t("dash.chain.content")} {chain.content_ok ? "✓" : "✗"}
                  </>
                )}
              </span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <ViewToggle mode={viewMode} onChange={changeView} />
          <button
            onClick={() => void onRecompute()}
            disabled={busy === "recompute"}
            className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
          >
            <RefreshCw
              className={`h-4 w-4 ${busy === "recompute" ? "animate-spin" : ""}`}
            />
            {t("dash.recompute")}
          </button>
        </div>
      </div>

      {error && state && (
        <div className="animate-fade-up mt-4 flex items-center gap-2 rounded-2xl border border-status-debilitada/25 bg-status-debilitadaBg px-4 py-3 text-[13px] text-status-debilitada">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Counts strip */}
      {s && (
        <div className="animate-fade-up mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <CountCard
            icon={ClipboardCheck}
            label={t("count.evidenceValidated")}
            value={s.evidence_validated ?? 0}
          />
          <CountCard
            icon={Clock}
            label={t("count.evidencePending")}
            value={s.evidence_pending ?? 0}
          />
          <CountCard
            icon={GitBranch}
            label={t("count.hypotheses")}
            value={s.hypotheses.length}
          />
          <CountCard
            icon={FlaskConical}
            label={t("count.experiments")}
            value={countValues(s.experiment_counts)}
          />
        </div>
      )}

      {/* Judge onboarding — dismissible quick tour */}
      <QuickTour />

      {/* The single next step — sentence rendered on the frontend from kind */}
      {s?.next_step && <NextStepCard next={s.next_step} />}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Rival hypotheses — self-fetches ALL hypotheses (incl. latent),
              which the SEALED state deliberately hides. */}
          <HypothesesPanel
            sealed={s?.hypotheses ?? []}
            revision={revision}
            onAdded={() => void refetch()}
          />

          {/* Vocational intake — seeds candidate hypotheses (pending) */}
          <IntakePanel onRegistered={() => void refetch()} />

          {/* Trajectories — vocational fit over the SEALED hypotheses */}
          <TrajectoriesPanel
            revision={revision}
            onChanged={() => void refetch()}
          />

          {/* Evidence ledger */}
          <Panel
            title={t("panel.evidence.title")}
            subtitle={t("panel.evidence.subtitle")}
            icon={ClipboardList}
          >
            {/* Honest disclosure, not an alarm: validated evidence that isn't
                linked to any hypothesis does not count until linked. */}
            {unlinked > 0 && (
              <p className="mb-3 flex items-start gap-1.5 text-[12px] leading-relaxed text-ink-500">
                <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
                {t("coverage.unlinked", { n: unlinked })}
              </p>
            )}
            {visibleEvidence.length > 0 ? (
              <div className="space-y-2">
                {visibleEvidence.map((e) => (
                  <EvidenceRow
                    key={e.id}
                    ev={e}
                    onValidate={() => void onValidate(e.id)}
                    validating={busy === `validate-${e.id}`}
                  />
                ))}
              </div>
            ) : (
              <Empty>{t("panel.evidence.empty")}</Empty>
            )}
          </Panel>

          {/* Narrative -> signals */}
          <ExtractPanel onValidated={() => void refetch()} />
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Self-perception vs. data — fixed template, no model */}
          <ConfrontationPanel data={confrontations} />

          {/* Narrator */}
          <NarratePanel language={narratorLanguage(lang)} />

          {/* Audit chain */}
          <Panel
            title={t("panel.chain.title")}
            subtitle={t("panel.chain.subtitle")}
            icon={ScrollText}
          >
            {chain ? (
              <AuditChain
                entries={chain.entries}
                linkageOk={chain.linkage_ok}
                integrityOk={chain.integrity_ok}
                contentOk={chain.content_ok}
              />
            ) : (
              <Empty>{t("panel.chain.empty")}</Empty>
            )}
          </Panel>
        </div>
      </div>
    </section>
    </DashboardErrorBoundary>
  );
}

/* ─────────────────────────── sub-components ─────────────────────────── */

function NextStepCard({ next }: { next: NextStep }) {
  const { t } = useI18n();
  const Icon = NEXT_STEP_ICON[next.kind] ?? FlaskConical;
  const sentence = nextStepSentence(t, next);
  return (
    <div className="animate-fade-up shadow-glow glass mt-6 flex items-start gap-4 rounded-3xl p-6">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl brand-gradient text-white">
        <Icon className="h-6 w-6" />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-brand-deep">
          {t("next.eyebrow")} · {next.kind.replace(/_/g, " ")}
        </p>
        <p className="mt-1 text-[16px] font-semibold leading-relaxed text-ink-900">
          {sentence}
        </p>
        <p className="mt-2 text-[11.5px] text-ink-400">{t("next.caption")}</p>
      </div>
    </div>
  );
}

function EvidenceRow({
  ev,
  onValidate,
  validating,
}: {
  ev: Evidence;
  onValidate: () => void;
  validating: boolean;
}) {
  const { t, lang } = useI18n();
  const pending = ev.validated !== 1;
  // Evidence type is a fixed enum → localized label; content is API-authored.
  const typeLabel = t(`evidenceType.${ev.evidence_type}` as never) || ev.evidence_type;
  return (
    <div className="card-solid flex flex-col gap-2 rounded-2xl p-3.5 sm:flex-row sm:items-center sm:gap-3">
      <div className="flex shrink-0 items-center gap-2">
        <span className="rounded-full bg-brand-indigo/10 px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
          {typeLabel}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12.5px] leading-snug text-ink-700">
          {contentSnippet(ev.content, 140, (str) => localizeSeed(str, lang))}
        </p>
        <p className="mt-0.5 text-[11px] text-ink-400">
          {ev.source} · {formatDate(ev.created_at)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {pending ? (
          <>
            <span className="inline-flex items-center gap-1 rounded-full bg-status-debilitadaBg px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide text-status-debilitada">
              <Clock className="h-3 w-3" />
              {t("pill.pending")}
            </span>
            <button
              onClick={onValidate}
              disabled={validating}
              className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
            >
              {validating ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              {t("btn.validate")}
            </button>
          </>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-status-corroboradaBg px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide text-status-corroborada">
            <CheckCircle2 className="h-3 w-3" />
            {t("pill.validated")}
          </span>
        )}
      </div>
    </div>
  );
}

function ExtractPanel({ onValidated }: { onValidated: () => void }) {
  const { t, lang } = useI18n();
  const [narrative, setNarrative] = useState("");
  const [candidates, setCandidates] = useState<ExtractCandidate[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validatingId, setValidatingId] = useState<string | number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    if (!narrative.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.extract(narrative, narratorLanguage(lang));
      setCandidates(res.candidates);
      setNote(res.note ?? null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.extract"));
    } finally {
      setBusy(false);
    }
  };

  const validate = async (id: string | number) => {
    setValidatingId(id);
    try {
      await api.validateEvidence(id);
      setCandidates((prev) => prev?.filter((c) => c.evidence_id !== id) ?? null);
      onValidated();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.validate"));
    } finally {
      setValidatingId(null);
    }
  };

  return (
    <Panel
      title={t("panel.extract.title")}
      subtitle={t("panel.extract.subtitle")}
      icon={Wand2}
    >
      {/* Example narratives — clicking a chip only fills the textarea. */}
      <ExampleChips
        hint={t("examples.narrativeHint")}
        examples={[
          t("example.narrative1"),
          t("example.narrative2"),
          t("example.narrative3"),
        ]}
        onPick={setNarrative}
      />
      <textarea
        value={narrative}
        onChange={(e) => setNarrative(e.target.value)}
        rows={4}
        placeholder={t("panel.extract.placeholder")}
        className="field-input mt-3 resize-y"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <button
          onClick={() => void run()}
          disabled={busy || !narrative.trim()}
          className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
        >
          {busy ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {t("panel.extract.action")}
        </button>
        {/* note is API-authored — rendered as-is */}
        {note && <span className="text-[11px] italic text-ink-400">{note}</span>}
      </div>

      {err && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {candidates && (
        <div className="mt-4 space-y-2">
          {candidates.length === 0 ? (
            <Empty>{t("panel.extract.empty")}</Empty>
          ) : (
            candidates.map((c) => (
              <div
                key={c.evidence_id}
                className="rounded-2xl border border-dashed border-brand-indigo/25 bg-brand-indigo/[0.03] p-3.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    {/* señal + cita are API-authored — rendered as-is */}
                    <p className="text-[13px] font-semibold text-ink-900">{c["señal"]}</p>
                    <p className="mt-1 border-l-2 border-brand-indigo/30 pl-2.5 text-[12px] italic leading-relaxed text-ink-500">
                      “{c.cita}”
                    </p>
                  </div>
                  <button
                    onClick={() => void validate(c.evidence_id)}
                    disabled={validatingId === c.evidence_id}
                    className="btn-ghost inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
                  >
                    {validatingId === c.evidence_id ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    )}
                    {t("btn.validate")}
                  </button>
                </div>
                <p className="mt-2 text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
                  {t("panel.extract.pendingTag")}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </Panel>
  );
}

function NarratePanel({ language }: { language: "English" | "Spanish" }) {
  const { t } = useI18n();
  const [result, setResult] = useState<NarrateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      // Pass the current UI language so the narrator responds in it.
      setResult(await api.narrate(language));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.narrate"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title={t("panel.narrator.title")}
      subtitle={t("panel.narrator.subtitle")}
      icon={Sparkles}
    >
      <button
        onClick={() => void run()}
        disabled={busy}
        className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
      >
        {busy ? (
          <RefreshCw className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        {t("panel.narrator.action")}
      </button>

      {err && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5" /> {err}
        </p>
      )}

      {result && (
        <div className="animate-fade-up mt-4">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-ink-900/5 px-2.5 py-1 font-mono text-[10.5px] text-ink-700">
            <ShieldCheck className="h-3 w-3 text-brand-indigo" />
            {t("dash.seal")} {shortHash(result.seal, 10, 6)}
          </div>
          {/* summary + prose are the narrator's own words — rendered as-is */}
          {result.summary && (
            <p className="mb-2 text-[12px] font-semibold text-ink-500">{result.summary}</p>
          )}
          <div className="glass-subtle rounded-2xl p-4 text-[13.5px] leading-relaxed text-ink-700">
            {result.prose}
          </div>
          <p className="mt-2 text-[11px] italic leading-relaxed text-ink-400">
            {t("panel.narrator.caption")}
          </p>
        </div>
      )}
    </Panel>
  );
}

// Shape the list renders — merged from /api/hypotheses (which lists EVERY
// hypothesis, including latent ones the sealed state hides) with the sealed
// index/status when the hypothesis exists there.
type DisplayHypothesis = {
  id: number | string;
  statement: string;
  status: StateHypothesis["status"];
  index: number | null;
  engine_version?: string;
};

function HypothesesPanel({
  sealed,
  revision,
  onAdded,
}: {
  sealed: StateHypothesis[];
  revision: number;
  onAdded: () => void;
}) {
  const { t, lang } = useI18n();
  const [statement, setStatement] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // The panel lists ALL hypotheses. A freshly added one is LATENT and is
  // deliberately absent from the sealed state (design doc §3.2), so listing
  // only the sealed subset made "Add hypothesis" look like it did nothing.
  const [all, setAll] = useState<Hypothesis[] | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const res = await api.getHypotheses();
      setAll(res.hypotheses);
    } catch {
      // Non-fatal: fall back to the sealed subset below.
      setAll(null);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll, revision]);

  const add = async () => {
    if (!statement.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.postHypothesis(statement.trim());
      setStatement("");
      await loadAll(); // reflect the new (latent) hypothesis immediately
      onAdded();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.hypothesis"));
    } finally {
      setBusy(false);
    }
  };

  // Overlay the sealed index/status onto the full list.
  const sealedById = new Map(sealed.map((h) => [String(h.id), h]));
  const display: DisplayHypothesis[] = (all ?? sealed).map((h) => {
    const s = sealedById.get(String(h.id));
    const idx = "index" in h ? (h as StateHypothesis).index : (h as Hypothesis).index_value;
    return {
      id: h.id,
      statement: h.statement,
      status: s?.status ?? h.status,
      index: s?.index ?? idx ?? null,
      engine_version: s?.engine_version ?? h.engine_version,
    };
  });

  return (
    <Panel
      title={t("panel.hypotheses.title")}
      subtitle={t("panel.hypotheses.subtitle")}
      icon={GitBranch}
    >
      {display.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {display.map((h) => (
            <div key={h.id} className="card-solid rounded-2xl p-4">
              <div className="flex items-center justify-between gap-2">
                <StatusChip status={h.status} />
                {h.engine_version && (
                  <span className="font-mono text-[10px] text-ink-400">
                    {h.engine_version}
                  </span>
                )}
              </div>
              {/* Hypothesis statement is user/API-authored; seed fixtures are
                  localized for display only (nothing written back is changed). */}
              <p
                className={`mt-3 text-[13.5px] leading-relaxed text-ink-700 ${
                  statusIsStruck(h.status) ? "line-through opacity-60" : ""
                }`}
              >
                {localizeSeed(h.statement, lang)}
              </p>
              <div className="mt-3 border-t border-ink-900/5 pt-3">
                <IndexGauge index={h.index} status={h.status} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty>{t("panel.hypotheses.empty")}</Empty>
      )}

      {/* Add a hypothesis, with example chips that only fill the input. */}
      <div className="mt-4 border-t border-ink-900/5 pt-4">
        <ExampleChips
          hint={t("examples.hypothesisHint")}
          examples={[t("example.hypothesis1"), t("example.hypothesis2")]}
          onPick={setStatement}
        />
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            value={statement}
            onChange={(e) => setStatement(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void add();
            }}
            placeholder={t("hypothesis.addPlaceholder")}
            className="field-input flex-1"
          />
          <button
            onClick={() => void add()}
            disabled={busy || !statement.trim()}
            className="btn-primary shadow-soft inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold"
          >
            {busy ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            {t("hypothesis.add")}
          </button>
        </div>
        {err && (
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-status-debilitada">
            <AlertCircle className="h-3.5 w-3.5" /> {err}
          </p>
        )}
      </div>
    </Panel>
  );
}

/* ─────────────────────────── primitives ─────────────────────────── */

function CountCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FlaskConical;
  label: string;
  value: number;
}) {
  return (
    <div className="card-solid rounded-2xl p-3.5">
      <div className="flex items-center gap-2 text-ink-400">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10.5px] font-bold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 font-display text-[26px] font-extrabold leading-none tracking-tight text-ink-900">
        {value}
      </p>
    </div>
  );
}

function countValues(counts?: Record<string, number>): number {
  if (!counts) return 0;
  return Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);
}

/* ─────────────────────────── states ─────────────────────────── */

function DashboardSkeleton() {
  return (
    <section className="mx-auto max-w-7xl px-4 pb-10 pt-6">
      <div className="skeleton h-9 w-64 rounded-lg" />
      <div className="mt-3 skeleton h-5 w-96 rounded-lg" />
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-20 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton mt-6 h-28 rounded-3xl" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <div className="skeleton h-72 rounded-3xl" />
          <div className="skeleton h-56 rounded-3xl" />
        </div>
        <div className="space-y-6">
          <div className="skeleton h-56 rounded-3xl" />
          <div className="skeleton h-72 rounded-3xl" />
        </div>
      </div>
    </section>
  );
}

function BackendUnreachable({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const { t } = useI18n();
  return (
    <section className="mx-auto flex max-w-2xl flex-col items-center px-4 pb-10 pt-20 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-status-debilitadaBg text-status-debilitada">
        <AlertCircle className="h-7 w-7" />
      </span>
      <h1 className="mt-5 font-display text-2xl font-extrabold tracking-tight text-ink-900">
        {t("err.backendTitle")}
      </h1>
      <p className="mt-2 max-w-md text-[14px] leading-relaxed text-ink-500">{message}</p>
      <div className="mt-4 rounded-2xl bg-ink-900/5 px-4 py-3 text-left font-mono text-[12px] text-ink-700">
        <p className="mb-1 text-ink-400">{t("err.backendHint")}</p>
        <p>NEXT_PUBLIC_API_URL={api.API_BASE}</p>
      </div>
      <button
        onClick={onRetry}
        className="btn-primary shadow-soft mt-5 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13px] font-bold"
      >
        <RefreshCw className="h-4 w-4" />
        {t("err.retry")}
      </button>
    </section>
  );
}

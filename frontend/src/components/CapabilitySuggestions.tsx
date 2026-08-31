"use client";

import { useState } from "react";
import {
  AlertCircle,
  BookOpen,
  ExternalLink,
  Globe,
  PencilRuler,
  RefreshCw,
  ShieldAlert,
  Compass as CompassIcon,
} from "lucide-react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useI18n, narratorLanguage } from "@/lib/i18n";
import { useAutoResize } from "@/lib/useAutoResize";
import { PendingHint } from "@/components/PendingHint";
import type {
  ExperimentDraft,
  ResourceKind,
  ResourcesResponse,
} from "@/lib/types";

/**
 * The two concrete suggestions the LLM makes about ONE open capability:
 * an experiment that would settle it, and where to go run it.
 *
 * Both are proposals with no authority. The draft is not preregistered
 * until the person presses the button; the resources are reading material
 * that never enters the ledger. Neither call moves an index — enforced
 * server-side by `test_suggesting_moves_no_sealed_number`.
 *
 * Two honesty rules this component exists to keep:
 *  - Resources say whether they were actually SEARCHED. A model listing
 *    things from memory is not a search, and must not look like one.
 *  - A resource with no URL renders as plain text. A link is only drawn
 *    when the backend actually returned one (and non-http schemes are
 *    already stripped at the API boundary).
 */

const KIND_ICON: Record<ResourceKind, typeof BookOpen> = {
  course: BookOpen,
  community: Globe,
  project: CompassIcon,
  reading: BookOpen,
  tool: PencilRuler,
  person: Globe,
};

export function CapabilitySuggestions({
  hypothesisId,
  onPreregistered,
}: {
  hypothesisId: number | string;
  onPreregistered: () => void;
}) {
  const { t, lang } = useI18n();
  const [draft, setDraft] = useState<ExperimentDraft | null>(null);
  const [resources, setResources] = useState<ResourcesResponse | null>(null);
  const [busy, setBusy] = useState<"design" | "resources" | "preregister" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const design = async () => {
    setBusy("design");
    setErr(null);
    try {
      setDraft((await api.designExperiment(hypothesisId, narratorLanguage(lang))).draft);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.design"));
    } finally {
      setBusy(null);
    }
  };

  const find = async () => {
    setBusy("resources");
    setErr(null);
    try {
      setResources(await api.findResources(hypothesisId, narratorLanguage(lang)));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.resources"));
    } finally {
      setBusy(null);
    }
  };

  // The draft becomes a real experiment only here, with whatever the person
  // edited it into.
  const preregister = async () => {
    if (!draft) return;
    setBusy("preregister");
    setErr(null);
    try {
      await api.postExperiment({ hypothesis_id: hypothesisId, ...draft });
      setDraft(null);
      onPreregistered();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("err.design"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mt-3 border-t border-ink-900/5 pt-3">
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => void design()}
          disabled={busy !== null}
          aria-busy={busy === "design"}
          className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
        >
          {busy === "design" ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <PencilRuler className="h-3.5 w-3.5" />
          )}
          {t("sugg.design")}
        </button>
        <button
          onClick={() => void find()}
          disabled={busy !== null}
          aria-busy={busy === "resources"}
          title={t("sugg.privacy")}
          className="btn-ghost inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] font-bold"
        >
          {busy === "resources" ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Globe className="h-3.5 w-3.5" />
          )}
          {t("sugg.resources")}
        </button>
      </div>

      {busy === "design" && <PendingHint hint={t("pending.design")} />}
      {busy === "resources" && <PendingHint hint={t("pending.resources")} />}

      {err && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] text-status-debilitada">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {err}
        </p>
      )}

      {draft && (
        <DraftEditor
          draft={draft}
          onChange={setDraft}
          onPreregister={() => void preregister()}
          onDiscard={() => setDraft(null)}
          busy={busy === "preregister"}
        />
      )}

      {resources && <ResourceList data={resources} />}
    </div>
  );
}

function DraftEditor({
  draft,
  onChange,
  onPreregister,
  onDiscard,
  busy,
}: {
  draft: ExperimentDraft;
  onChange: (d: ExperimentDraft) => void;
  onPreregister: () => void;
  onDiscard: () => void;
  busy: boolean;
}) {
  const { t } = useI18n();

  return (
    <div className="mt-3 rounded-2xl bg-brand-indigo/[0.06] p-3.5">
      <p className="text-[10.5px] font-bold uppercase tracking-wide text-brand-deep">
        {t("sugg.draftTitle")}
      </p>
      <p className="mb-3 mt-1 text-[11.5px] leading-relaxed text-ink-600">
        {t("sugg.draftNote")}
      </p>
      <div className="space-y-2.5">
        <AutoField
          label={t("sugg.design.label")}
          value={draft.design}
          onChange={(v) => onChange({ ...draft, design: v })}
        />
        <AutoField
          label={t("sugg.success.label")}
          value={draft.success_criterion}
          onChange={(v) => onChange({ ...draft, success_criterion: v })}
        />
        <AutoField
          label={t("sugg.failure.label")}
          hint={t("sugg.failureNote")}
          value={draft.failure_criterion}
          onChange={(v) => onChange({ ...draft, failure_criterion: v })}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={onPreregister}
          disabled={busy}
          className="btn-primary shadow-soft inline-flex items-center gap-2 rounded-full px-4 py-2 text-[12.5px] font-bold"
        >
          {busy && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
          {t("sugg.preregister")}
        </button>
        <button
          onClick={onDiscard}
          disabled={busy}
          className="btn-ghost rounded-full px-4 py-2 text-[12.5px] font-bold"
        >
          {t("sugg.discard")}
        </button>
      </div>
    </div>
  );
}

// Editable draft field that grows to fit its content — no inner scrollbox, so
// the whole experiment reads at a glance. min-height keeps short text roomy.
function AutoField({
  label,
  value,
  hint,
  onChange,
}: {
  label: string;
  value: string;
  hint?: string;
  onChange: (v: string) => void;
}) {
  const ref = useAutoResize<HTMLTextAreaElement>(value);
  return (
    <label className="block">
      <span className="mb-1 block text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        {label}
      </span>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="field-input w-full resize-none overflow-hidden leading-relaxed"
        style={{ minHeight: "5rem" }}
      />
      {hint && <span className="mt-1 block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

function ResourceList({ data }: { data: ResourcesResponse }) {
  const { t } = useI18n();
  return (
    <div className="mt-3 rounded-2xl bg-ink-900/[0.02] p-3.5">
      <p className="text-[10.5px] font-bold uppercase tracking-wide text-ink-400">
        {t("sugg.resourcesTitle")}
      </p>

      {/* Searched or remembered — never left ambiguous. */}
      <p
        className={`mt-1 flex items-start gap-1.5 text-[11.5px] leading-relaxed ${
          data.grounded ? "text-ink-500" : "text-status-debilitada"
        }`}
      >
        {!data.grounded && <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
        {data.grounded ? t("sugg.grounded") : t("sugg.notGrounded")}
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-ink-500">
        {t("sugg.resourcesNote")}
      </p>

      {data.resources.length === 0 ? (
        <p className="mt-3 text-[12.5px] text-ink-500">{t("sugg.noResources")}</p>
      ) : (
        <div className="mt-3 space-y-2">
          {data.resources.map((r, i) => {
            const Icon = KIND_ICON[r.kind] ?? BookOpen;
            return (
              <div key={`${r.title}-${i}`} className="card-solid rounded-xl p-3">
                <div className="flex items-start gap-2">
                  <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-indigo" />
                  <div className="min-w-0 flex-1">
                    {/* Third-party text: rendered as content, never executed. */}
                    <p className="text-[12.5px] font-bold text-ink-900">{r.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-ink-600">
                      {r.why}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="rounded-full bg-ink-900/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-500">
                        {t(`kind.${r.kind}` as never) || r.kind}
                      </span>
                      {/* Only linked when a real URL came back. */}
                      {r.url && (
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-deep hover:underline"
                        >
                          <ExternalLink className="h-3 w-3" />
                          {new URL(r.url).hostname}
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {data.sources.length > 0 && (
        <div className="mt-3 border-t border-ink-900/5 pt-2">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-ink-400">
            {t("sugg.sources")}
          </p>
          <ul className="space-y-0.5">
            {data.sources.map((srcItem) => (
              <li key={srcItem.uri}>
                <a
                  href={srcItem.uri}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="text-[11px] text-ink-500 hover:underline"
                >
                  {srcItem.title || new URL(srcItem.uri).hostname}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

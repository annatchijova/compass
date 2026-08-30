// COMPASS API client. Thin fetch wrappers around the backend contract.
// Base URL from NEXT_PUBLIC_API_URL (inlined at build), default localhost:8080.

import type {
  Health,
  StateResponse,
  EvidenceResponse,
  HypothesesResponse,
  ExperimentsResponse,
  ChainResponse,
  RecomputeResponse,
  ExtractResponse,
  NarrateResponse,
  AbduceResponse,
  EvidenceType,
  TrajectoriesResponse,
  FitResponse,
  DiscriminateResponse,
} from "./types";
import { getUserId } from "./session";

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").replace(/\/$/, "");

/** Raised when the backend is unreachable or returns a non-2xx status. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Identify which isolated compass this request reads/writes. Read from
  // localStorage at call time; empty on the server (SSR) — all callers here
  // are client components, so a real id is present in the browser.
  const userId = getUserId();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(userId ? { "X-Compass-User": userId } : {}),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError(
      `Cannot reach the COMPASS backend at ${API_BASE}. Is it running?`,
      0,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      /* ignore */
    }
    throw new ApiError(
      `Request to ${path} failed (${res.status}). ${detail.slice(0, 200)}`,
      res.status,
    );
  }
  return (await res.json()) as T;
}

// ---- reads ----
export const getHealth = () => request<Health>("/health");
export const getState = () => request<StateResponse>("/api/state");
export const getEvidence = () => request<EvidenceResponse>("/api/evidence");
export const getHypotheses = () => request<HypothesesResponse>("/api/hypotheses");
export const getExperiments = () => request<ExperimentsResponse>("/api/experiments");
export const getChain = () => request<ChainResponse>("/api/chain");

// ---- writes ----
export const postEvidence = (body: {
  evidence_type: EvidenceType;
  source: string;
  content: Record<string, unknown>;
  validated: boolean;
}) =>
  request<{ evidence_id: number | string; validated: boolean }>("/api/evidence", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const validateEvidence = (id: number | string) =>
  request<{ evidence_id: number | string; validated: true }>(
    `/api/evidence/${id}/validate`,
    { method: "POST" },
  );

export const forgetEvidence = (id: number | string, reason: string) =>
  request<{ evidence_id: number | string; tombstoned: true }>(
    `/api/evidence/${id}/forget`,
    { method: "POST", body: JSON.stringify({ reason }) },
  );

export const postHypothesis = (statement: string) =>
  request<{ hypothesis_id: number | string }>("/api/hypotheses", {
    method: "POST",
    body: JSON.stringify({ statement }),
  });

export const postLink = (body: {
  hypothesis_id: number | string;
  evidence_id: number | string;
  direction: "supports" | "contradicts";
}) =>
  request<{ linked: true }>("/api/link", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const postExperiment = (body: {
  hypothesis_id: number | string;
  design: string;
  success_criterion: string;
  failure_criterion: string;
  rival_hypothesis_id?: number | string;
  duration?: string | number;
}) =>
  request<{ experiment_id: number | string }>("/api/experiments", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const completeExperiment = (
  id: number | string,
  body: { outcome: "exito" | "fracaso" | "inconcluso"; notes?: string },
) =>
  request<{ experiment_id: number | string; generated_evidence_id: number | string }>(
    `/api/experiments/${id}/complete`,
    { method: "POST", body: JSON.stringify(body) },
  );

export const recompute = () =>
  request<RecomputeResponse>("/api/recompute", { method: "POST" });

export const extract = (narrative: string) =>
  request<ExtractResponse>("/api/extract", {
    method: "POST",
    body: JSON.stringify({ narrative }),
  });

export const abduce = () =>
  request<AbduceResponse>("/api/abduce", { method: "POST" });

// The narrator responds in the requested language. The endpoint accepts a
// `language` query param with values exactly "English" or "Spanish"
// (default English). This only affects the narrator's WORDS — never the
// seal or any index, which are fixed before narration.
export const narrate = (language: "English" | "Spanish" = "English") =>
  request<NarrateResponse>(
    `/api/narrate?language=${encodeURIComponent(language)}`,
    { method: "POST" },
  );

/* ─────────────────────────── Trajectories ─────────────────────────── */

export const getTrajectories = () =>
  request<TrajectoriesResponse>("/api/trajectories");

export const postTrajectory = (body: { name: string; description?: string }) =>
  request<{ trajectory_id: number | string }>("/api/trajectories", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const postRequirement = (
  trajectoryId: number | string,
  body: { hypothesis_id: number | string; label: string },
) =>
  request<{ requirement_id: number | string }>(
    `/api/trajectories/${trajectoryId}/requirements`,
    { method: "POST", body: JSON.stringify(body) },
  );

export const getFit = (trajectoryId: number | string) =>
  request<FitResponse>(`/api/trajectories/${trajectoryId}/fit`);

export const getDiscriminate = (a: number | string, b: number | string) =>
  request<DiscriminateResponse>(
    `/api/trajectories/discriminate?a=${encodeURIComponent(String(a))}&b=${encodeURIComponent(String(b))}`,
  );

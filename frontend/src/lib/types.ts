// COMPASS API contract types. Mirrors the backend response shapes.

export type HypothesisStatus =
  | "latente"
  | "activa"
  | "corroborada"
  | "debilitada"
  | "descartada";

export type NextStepKind =
  | "completar_experimento"
  | "ejecutar_experimento"
  | "validar_evidencia"
  | "diseñar_experimento"
  | "abstain";

export type EvidenceType =
  | "self_report"
  | "narrative_extracted"
  | "behavioral"
  | "experiment_result"
  | "outcome_external";

export interface Health {
  status: string;
  llm_backend?: string;
  model?: string;
  gemini_transport?: string;
  db_durability?: string;
  seeded?: boolean;
  chain_linkage_ok?: boolean;
  chain_integrity_ok?: boolean;
}

export interface StateHypothesis {
  id: number | string;
  statement: string;
  status: HypothesisStatus;
  index: number | null;
  engine_version?: string;
}

export interface NextStep {
  kind: NextStepKind;
  detail: string;
  [key: string]: unknown;
}

export interface CompassState {
  person?: string;
  hypotheses: StateHypothesis[];
  hypothesis_counts?: Record<string, number>;
  experiment_counts?: Record<string, number>;
  evidence_validated?: number;
  evidence_pending?: number;
  next_step: NextStep;
}

export interface StateResponse {
  state: CompassState;
  seal: string;
}

export interface Evidence {
  id: number | string;
  evidence_type: EvidenceType;
  source: string;
  content: string; // JSON string
  validated: 0 | 1;
  deleted: 0 | 1;
  created_at?: string;
  validated_at?: string | null;
}

export interface EvidenceResponse {
  evidence: Evidence[];
}

export interface Hypothesis {
  id: number | string;
  statement: string;
  status: HypothesisStatus;
  origin?: string;
  index_value: number | null;
  engine_version?: string;
}

export interface HypothesesResponse {
  hypotheses: Hypothesis[];
}

export interface Experiment {
  id: number | string;
  hypothesis_id: number | string;
  design: string;
  success_criterion: string;
  failure_criterion: string;
  rival_hypothesis_id?: number | string | null;
  status: string;
  preregistered_at?: string;
  completed_at?: string | null;
}

export interface ExperimentsResponse {
  experiments: Experiment[];
}

export interface ChainEntry {
  seq: number;
  op: string;
  ts: string;
  audit_hash: string;
  prev_hash: string;
}

export interface ChainResponse {
  entries: ChainEntry[];
  linkage_ok: boolean;
  integrity_ok: boolean;
  issues: unknown[];
}

export interface RecomputeResult {
  hypothesis_id: number | string;
  support: number;
  contra: number;
  net: number;
  index: number;
  status: HypothesisStatus;
}

export interface RecomputeResponse {
  engine_version: string;
  config_hash: string;
  results: RecomputeResult[];
  seal: string;
}

export interface ExtractCandidate {
  evidence_id: number | string;
  "señal": string;
  cita: string;
}

export interface ExtractResponse {
  candidates: ExtractCandidate[];
  note?: string;
}

export interface NarrateResponse {
  seal: string;
  summary?: string;
  prose: string;
}

export interface AbduceProposal {
  statement: string;
}

export interface AbduceResponse {
  proposals: AbduceProposal[];
  state_seal: string;
}

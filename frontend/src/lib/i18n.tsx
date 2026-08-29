"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import type { NextStep, NextStepKind } from "@/lib/types";

export type Lang = "en" | "es";

// English is the primary language. Spanish is a faithful Rioplatense
// (voseo, professional, neutral) translation of the UI CHROME only.
// User-authored content (hypothesis statements, evidence content, extractor
// candidate values) is NEVER translated here — it is rendered as-authored.
const dict = {
  en: {
    // Nav
    "nav.how": "How it works",
    "nav.dashboard": "Open dashboard",

    // Footer
    "footer.rights": "© 2026 COMPASS · No claim without sealed evidence",
    "footer.tag": "Deterministic engine · Hash-chained ledger",

    // Landing
    "landing.badge": "Adaptive personal navigation",
    "landing.title1": "Evidence, not flattery.",
    "landing.title2": "A compass, not a mirror.",
    "landing.subtitle":
      "COMPASS is a navigation partner bound by two invariants: no claim about you exists without sealed evidence, and no number describing you ever comes out of a language model. A deterministic engine computes and seals every index before any model is allowed to speak.",
    "landing.cta": "Open the dashboard",
    "landing.ctaSecondary": "How it works",

    "landing.feature1.title": "Sealed evidence ledger",
    "landing.feature1.desc":
      "No claim about the person exists without recorded, sealed evidence. Every assertion is appended to an append-only, hash-chained audit ledger you can verify.",
    "landing.feature2.title": "No number from an LLM",
    "landing.feature2.desc":
      "A deterministic engine computes and seals every confidence index before any model speaks. The narrator only puts fixed figures into words — it can never move them.",
    "landing.feature3.title": "Rival hypotheses, discriminating experiments",
    "landing.feature3.desc":
      "Competing explanations are held alive until a preregistered experiment separates them. Contradicting evidence weighs more than confirming — a compass, not a mirror.",

    "landing.stat1.title": "Deterministic core",
    "landing.stat1.desc": "The index is sealed before the LLM narrates.",
    "landing.stat2.title": "Anti-flattery",
    "landing.stat2.desc": "Contradicting evidence weighs more than confirming.",
    "landing.stat3.title": "Audit ledger",
    "landing.stat3.desc": "Append-only, hash-chained, independently verifiable.",

    "landing.cycle.title": "The abductive cycle",
    "landing.cycle.note": "rival hypotheses held alive until an experiment separates them",
    "landing.cycle.tag": "index sealed before narration",

    "landing.dial.caption":
      "an integer accumulation of evidence under versioned rules — never a probability",
    "landing.dial.label": "confidence index",

    // Dashboard header
    "dash.eyebrow": "Navigation dashboard",
    "dash.person.fallback": "Person",
    "dash.seal": "seal",
    "dash.chain.linkage": "linkage",
    "dash.chain.integrity": "integrity",
    "dash.chain.content": "content",
    "dash.chainPrefix": "chain:",
    "dash.recompute": "Recompute & reseal",

    // Counts
    "count.evidenceValidated": "Evidence validated",
    "count.evidencePending": "Evidence pending",
    "count.hypotheses": "Hypotheses",
    "count.experiments": "Experiments",

    // Next step
    "next.eyebrow": "The single next step",
    "next.caption": "Deterministic recommendation — computed by the engine, not the narrator.",

    // Panels
    "panel.hypotheses.title": "Rival hypotheses",
    "panel.hypotheses.subtitle": "Held alive until a discriminating experiment separates them",
    "panel.hypotheses.empty": "No hypotheses yet.",

    "panel.evidence.title": "Evidence ledger",
    "panel.evidence.subtitle": "Nothing counts until it is validated",
    "panel.evidence.empty": "No evidence recorded yet.",
    "coverage.unlinked":
      "{n} validated evidence not yet linked to any hypothesis — it does not count until linked.",

    "panel.extract.title": "Narrative → signals",
    "panel.extract.subtitle":
      "Extracted candidates persist as PENDING evidence — nothing counts until validated",
    "panel.extract.placeholder": "Paste a narrative in the person's own words…",
    "panel.extract.action": "Extract signals",
    "panel.extract.empty": "No signals extracted.",
    "panel.extract.pendingTag": "pending — does not count until validated",

    "panel.narrator.title": "Narrator",
    "panel.narrator.subtitle": "The seal exists before the narrator speaks",
    "panel.narrator.action": "Narrate my state",
    "panel.narrator.caption":
      "The seal exists before the narrator speaks; swapping the model changes only these words — never the seal or any index.",

    "panel.chain.title": "Audit chain",
    "panel.chain.subtitle": "Append-only, hash-chained ledger",
    "panel.chain.empty": "Chain unavailable.",

    // Evidence types
    "evidenceType.self_report": "self report",
    "evidenceType.narrative_extracted": "narrative",
    "evidenceType.behavioral": "behavioral",
    "evidenceType.experiment_result": "experiment",
    "evidenceType.outcome_external": "outcome",

    // Hypothesis statuses (chip labels) — the API status values are internal
    // Spanish enum identifiers; these are their localized DISPLAY labels.
    "status.latente": "Latent",
    "status.activa": "Active",
    "status.corroborada": "Corroborated",
    "status.debilitada": "Weakened",
    "status.descartada": "Discarded",

    // Index gauge
    "gauge.label": "confidence index",
    "gauge.caption": "accumulation of evidence under versioned rules — not a probability",
    "gauge.unit": "/ 1000",

    // Audit chain component
    "chain.linkage": "linkage",
    "chain.integrity": "integrity",
    "chain.content": "content",
    "chain.entries": "entries",
    "chain.prev": "prev",
    "chain.emptyTitle": "No ledger entries yet",
    "chain.emptyDesc":
      "Every claim about the person appends a sealed entry here. Nothing has been recorded.",

    // Common pills / buttons
    "pill.pending": "pending",
    "pill.validated": "validated",
    "btn.validate": "Validate",

    // Errors
    "err.load": "Something went wrong loading the dashboard.",
    "err.trajectory": "Could not add the trajectory.",
    "err.trajectoryFit": "Could not load the trajectory fit.",
    "err.requirement": "Could not add the requirement.",
    "err.discriminate": "Could not compare the trajectories.",
    "err.refetch": "Refetch failed.",
    "err.validate": "Validation failed.",
    "err.recompute": "Recompute failed.",
    "err.extract": "Extraction failed.",
    "err.narrate": "Narration failed.",
    "err.backendTitle": "Can't reach the COMPASS backend",
    "err.backendHint": "# start the backend, then retry",
    "err.retry": "Retry",

    // Next-step sentences (rendered on the frontend from next_step.kind)
    "nextStep.completar_experimento":
      "Record observations and close experiment #{id} against its preregistered criteria.",
    "nextStep.ejecutar_experimento": "Run the already-preregistered experiment #{id}.",
    "nextStep.validar_evidencia":
      "{count} evidence candidate(s) await validation: review, edit, or reject them.",
    "nextStep.disenar_experimento":
      "Design a discriminating experiment for hypothesis #{id}: it is the active one with the least evidence.",
    "nextStep.abstain":
      "No computable next step under the v0 rules: record evidence or a hypothesis.",

    // Judge onboarding — quick tour
    "tour.badge": "Quick tour",
    "tour.title": "New here? Try this in 60 seconds.",
    "tour.step1":
      "Pick an example narrative below and click Extract signals — Gemini proposes candidate signals. Nothing counts yet.",
    "tour.step2":
      "Validate a candidate you agree with — only your validation makes evidence real (the model has no authority).",
    "tour.step3": "Add a hypothesis (or use an example) and link evidence to it.",
    "tour.step4":
      "Click Recompute & reseal — watch the integer index (0–1000) move. It is computed and sealed by the deterministic engine, never by the model.",
    "tour.step5":
      "Click Narrate — Gemini puts the sealed state into words. Switch the language toggle and narrate again: the words change, the seal and the numbers do not.",
    "tour.step6":
      "Open the audit chain — every step is hash-chained; linkage and integrity verify independently.",
    "tour.dismiss": "Dismiss",
    "tour.show": "Show quick tour",

    // Example inputs (clickable chips)
    "examples.label": "Examples",
    "examples.narrativeHint": "Click an example to fill the box:",
    "examples.hypothesisHint": "Or start from an example:",

    // Add-hypothesis input
    "hypothesis.addPlaceholder": "State a hypothesis about the person…",
    "hypothesis.add": "Add hypothesis",
    "err.hypothesis": "Could not add the hypothesis.",

    // Example narratives (fill the extract textarea on click)
    "example.narrative1":
      "Whenever a system feels wrong I can't leave it — I rewrote our whole auth layer over a weekend nobody asked me to, just because the seams bothered me.",
    "example.narrative2":
      "I freeze in big meetings, but give me one person and a whiteboard and I'll redesign the thing from first principles in an hour.",
    "example.narrative3":
      "I finish other people's half-built projects fast, but I've never shipped one that started from a blank page — I don't know if that's a real gap or just untested.",

    // Example hypotheses (fill the add-hypothesis input on click)
    "example.hypothesis1": "Has strong systems-design capability under low social load.",
    "example.hypothesis2":
      "Learns fastest by finishing and repairing existing systems, not from a blank page.",

    // Trajectories (vocational fit) — counts per state, never a percentage
    "panel.traj.title": "Trajectories",
    "panel.traj.subtitle":
      "Vocational fit: what a path requires vs. what your evidence shows",
    "panel.traj.empty": "No trajectories yet. Name a path you are weighing.",
    "traj.readonly":
      "A fit is a projection over already-sealed hypotheses. Opening it recomputes nothing and moves no index.",
    "traj.noPercentage": "Counts per requirement — never a destiny percentage.",
    "traj.select": "Trajectory",
    "traj.addPlaceholder": "name a path you are weighing",
    "traj.add": "Add trajectory",
    "traj.requirements": "Capability requirements",
    "traj.req.empty":
      "No requirements yet. Add the capabilities this path demands — each backed by a hypothesis.",
    "traj.req.labelPlaceholder": "capability this path requires",
    "traj.req.hypothesis": "Backed by hypothesis",
    "traj.req.add": "Add requirement",
    "traj.req.needHypothesis":
      "Add a hypothesis first — a requirement must be backed by one.",
    "traj.req.allUsed":
      "Every hypothesis already backs a requirement here. Add a new hypothesis to add another.",
    "traj.req.backedBy": "hypothesis #{id}",
    "fit.met": "Met",
    "fit.supported": "Supported",
    "fit.open": "Open",
    "fit.against": "Against",
    "fit.discarded": "Discarded",
    "fit.total": "requirements",
    "traj.disc.title": "Which path does the next experiment separate?",
    "traj.disc.pickTwo": "Pick two different trajectories to compare.",
    "traj.disc.run": "Find the discriminating capability",
    "traj.disc.suggested": "Cheapest capability to test next",
    "traj.disc.onlyIn": "required only by {name}",
    "traj.disc.shared": "{n} requirement(s) shared by both",
    "traj.disc.distinguishing": "Distinguishing capabilities",
    "traj.disc.none":
      "No open capability separates these two right now.",
    "examples.trajectoryHint": "tap to fill",
    "example.trajectory1": "Systems engineer on small, high-trust teams",
    "example.trajectory2": "Independent researcher / technical writer",

    // Compass ID control
    "user.button": "Compass ID",
    "user.title": "Your Compass ID",
    "user.explainer":
      "Your compass is private to this ID. Save it to return to this compass; share nothing you don't want linked.",
    "user.currentLabel": "Current ID",
    "user.copy": "Copy",
    "user.copied": "Copied",
    "user.setLabel": "Set a custom ID",
    "user.setPlaceholder": "paste an ID to load its compass",
    "user.apply": "Load compass",
    "user.new": "New compass",
    "user.invalid": "Use 1–64 characters: letters, digits, hyphen or underscore.",
    "user.close": "Close",
  },
  es: {
    // Nav
    "nav.how": "Cómo funciona",
    "nav.dashboard": "Abrir dashboard",

    // Footer
    "footer.rights": "© 2026 COMPASS · Ninguna afirmación sin evidencia sellada",
    "footer.tag": "Motor determinista · Ledger encadenado por hash",

    // Landing
    "landing.badge": "Navegación personal adaptativa",
    "landing.title1": "Evidencia, no adulación.",
    "landing.title2": "Una brújula, no un espejo.",
    "landing.subtitle":
      "COMPASS es un socio de navegación regido por dos invariantes: ninguna afirmación sobre vos existe sin evidencia sellada, y ningún número que te describe sale jamás de un modelo de lenguaje. Un motor determinista calcula y sella cada índice antes de que cualquier modelo pueda hablar.",
    "landing.cta": "Abrir el dashboard",
    "landing.ctaSecondary": "Cómo funciona",

    "landing.feature1.title": "Ledger de evidencia sellada",
    "landing.feature1.desc":
      "Ninguna afirmación sobre la persona existe sin evidencia registrada y sellada. Cada aserción se agrega a un ledger de auditoría de solo agregado, encadenado por hash, que podés verificar.",
    "landing.feature2.title": "Ningún número sale del LLM",
    "landing.feature2.desc":
      "Un motor determinista calcula y sella cada índice de confianza antes de que un modelo hable. El narrador solo pone en palabras cifras ya fijadas — nunca puede moverlas.",
    "landing.feature3.title": "Hipótesis rivales, experimentos discriminantes",
    "landing.feature3.desc":
      "Las explicaciones que compiten se mantienen vivas hasta que un experimento preregistrado las separa. La evidencia que contradice pesa más que la que confirma — una brújula, no un espejo.",

    "landing.stat1.title": "Núcleo determinista",
    "landing.stat1.desc": "El índice se sella antes de que el LLM narre.",
    "landing.stat2.title": "Anti-adulación",
    "landing.stat2.desc": "La evidencia que contradice pesa más que la que confirma.",
    "landing.stat3.title": "Ledger de auditoría",
    "landing.stat3.desc": "De solo agregado, encadenado por hash, verificable de forma independiente.",

    "landing.cycle.title": "El ciclo abductivo",
    "landing.cycle.note": "las hipótesis rivales se mantienen vivas hasta que un experimento las separa",
    "landing.cycle.tag": "índice sellado antes de narrar",

    "landing.dial.caption":
      "una acumulación entera de evidencia bajo reglas versionadas — nunca una probabilidad",
    "landing.dial.label": "índice de confianza",

    // Dashboard header
    "dash.eyebrow": "Dashboard de navegación",
    "dash.person.fallback": "Persona",
    "dash.seal": "sello",
    "dash.chain.linkage": "encadenado",
    "dash.chain.integrity": "integridad",
    "dash.chain.content": "contenido",
    "dash.chainPrefix": "cadena:",
    "dash.recompute": "Recalcular y resellar",

    // Counts
    "count.evidenceValidated": "Evidencia validada",
    "count.evidencePending": "Evidencia pendiente",
    "count.hypotheses": "Hipótesis",
    "count.experiments": "Experimentos",

    // Next step
    "next.eyebrow": "El único paso siguiente",
    "next.caption": "Recomendación determinista — calculada por el motor, no por el narrador.",

    // Panels
    "panel.hypotheses.title": "Hipótesis rivales",
    "panel.hypotheses.subtitle": "Se mantienen vivas hasta que un experimento discriminante las separa",
    "panel.hypotheses.empty": "Todavía no hay hipótesis.",

    "panel.evidence.title": "Ledger de evidencia",
    "panel.evidence.subtitle": "Nada cuenta hasta que se valida",
    "panel.evidence.empty": "Todavía no hay evidencia registrada.",
    "coverage.unlinked":
      "{n} evidencia(s) validada(s) sin vincular a ninguna hipótesis — no cuenta hasta vincularla.",

    "panel.extract.title": "Narrativa → señales",
    "panel.extract.subtitle":
      "Los candidatos extraídos persisten como evidencia PENDIENTE — nada cuenta hasta validarlo",
    "panel.extract.placeholder": "Pegá una narrativa en las palabras de la propia persona…",
    "panel.extract.action": "Extraer señales",
    "panel.extract.empty": "No se extrajeron señales.",
    "panel.extract.pendingTag": "pendiente — no cuenta hasta validarlo",

    "panel.narrator.title": "Narrador",
    "panel.narrator.subtitle": "El sello existe antes de que el narrador hable",
    "panel.narrator.action": "Narrar mi estado",
    "panel.narrator.caption":
      "El sello existe antes de que el narrador hable; cambiar el modelo cambia solo estas palabras — nunca el sello ni ningún índice.",

    "panel.chain.title": "Cadena de auditoría",
    "panel.chain.subtitle": "Ledger de solo agregado, encadenado por hash",
    "panel.chain.empty": "Cadena no disponible.",

    // Evidence types
    "evidenceType.self_report": "autorreporte",
    "evidenceType.narrative_extracted": "narrativa",
    "evidenceType.behavioral": "conductual",
    "evidenceType.experiment_result": "experimento",
    "evidenceType.outcome_external": "resultado",

    // Hypothesis statuses (chip labels) — display labels for the API's
    // internal Spanish enum identifiers.
    "status.latente": "Latente",
    "status.activa": "Activa",
    "status.corroborada": "Corroborada",
    "status.debilitada": "Debilitada",
    "status.descartada": "Descartada",

    // Index gauge
    "gauge.label": "índice de confianza",
    "gauge.caption": "acumulación de evidencia bajo reglas versionadas — no una probabilidad",
    "gauge.unit": "/ 1000",

    // Audit chain component
    "chain.linkage": "encadenado",
    "chain.integrity": "integridad",
    "chain.content": "contenido",
    "chain.entries": "entradas",
    "chain.prev": "prev",
    "chain.emptyTitle": "Todavía no hay entradas en el ledger",
    "chain.emptyDesc":
      "Cada afirmación sobre la persona agrega acá una entrada sellada. No se registró nada.",

    // Common pills / buttons
    "pill.pending": "pendiente",
    "pill.validated": "validada",
    "btn.validate": "Validar",

    // Errors
    "err.load": "Algo salió mal al cargar el dashboard.",
    "err.trajectory": "No se pudo agregar la trayectoria.",
    "err.trajectoryFit": "No se pudo cargar el fit de la trayectoria.",
    "err.requirement": "No se pudo agregar el requisito.",
    "err.discriminate": "No se pudieron comparar las trayectorias.",
    "err.refetch": "Falló la recarga.",
    "err.validate": "Falló la validación.",
    "err.recompute": "Falló el recálculo.",
    "err.extract": "Falló la extracción.",
    "err.narrate": "Falló la narración.",
    "err.backendTitle": "No se puede alcanzar el backend de COMPASS",
    "err.backendHint": "# iniciá el backend y reintentá",
    "err.retry": "Reintentar",

    // Next-step sentences (rendered on the frontend from next_step.kind)
    "nextStep.completar_experimento":
      "Registrá las observaciones y cerrá el experimento #{id} contra sus criterios preregistrados.",
    "nextStep.ejecutar_experimento": "Ejecutá el experimento ya preregistrado #{id}.",
    "nextStep.validar_evidencia":
      "{count} candidato(s) de evidencia esperan validación: revisalos, editalos o rechazalos.",
    "nextStep.disenar_experimento":
      "Diseñá un experimento discriminante para la hipótesis #{id}: es la activa con menos evidencia.",
    "nextStep.abstain":
      "No hay paso siguiente computable bajo las reglas v0: registrá evidencia o una hipótesis.",

    // Onboarding para jueces — tour rápido
    "tour.badge": "Tour rápido",
    "tour.title": "¿Primera vez? Probá esto en 60 segundos.",
    "tour.step1":
      "Elegí una narrativa de ejemplo de abajo y tocá Extraer señales — Gemini propone señales candidatas. Todavía no cuenta nada.",
    "tour.step2":
      "Validá una candidata con la que estés de acuerdo — solo tu validación vuelve real a la evidencia (el modelo no tiene autoridad).",
    "tour.step3": "Agregá una hipótesis (o usá un ejemplo) y vinculá evidencia con ella.",
    "tour.step4":
      "Tocá Recalcular y resellar — mirá cómo se mueve el índice entero (0–1000). Lo calcula y lo sella el motor determinista, nunca el modelo.",
    "tour.step5":
      "Tocá Narrar — Gemini pone en palabras el estado sellado. Cambiá el toggle de idioma y narrá de nuevo: cambian las palabras, el sello y los números no.",
    "tour.step6":
      "Abrí la cadena de auditoría — cada paso está encadenado por hash; el encadenado y la integridad se verifican de forma independiente.",
    "tour.dismiss": "Descartar",
    "tour.show": "Ver tour rápido",

    // Entradas de ejemplo (chips clicables)
    "examples.label": "Ejemplos",
    "examples.narrativeHint": "Tocá un ejemplo para completar el campo:",
    "examples.hypothesisHint": "O arrancá desde un ejemplo:",

    // Campo para agregar hipótesis
    "hypothesis.addPlaceholder": "Enunciá una hipótesis sobre la persona…",
    "hypothesis.add": "Agregar hipótesis",
    "err.hypothesis": "No se pudo agregar la hipótesis.",

    // Narrativas de ejemplo (completan el textarea de extracción al tocar)
    "example.narrative1":
      "Cuando un sistema me huele mal no puedo soltarlo — reescribí toda nuestra capa de auth en un fin de semana que nadie me pidió, solo porque las costuras me molestaban.",
    "example.narrative2":
      "Me congelo en las reuniones grandes, pero dame una persona y un pizarrón y te rediseño la cosa desde primeros principios en una hora.",
    "example.narrative3":
      "Termino rápido los proyectos a medio construir de otros, pero nunca saqué uno que arrancara desde una hoja en blanco — no sé si es una carencia real o solo algo que no probé.",

    // Hipótesis de ejemplo (completan el campo de agregar hipótesis al tocar)
    "example.hypothesis1": "Tiene fuerte capacidad de diseño de sistemas bajo baja carga social.",
    "example.hypothesis2":
      "Aprende más rápido terminando y reparando sistemas existentes que desde una hoja en blanco.",

    // Trayectorias (fit vocacional) — cuentas por estado, nunca un porcentaje
    "panel.traj.title": "Trayectorias",
    "panel.traj.subtitle":
      "Fit vocacional: lo que un camino exige vs. lo que muestra tu evidencia",
    "panel.traj.empty": "Todavía no hay trayectorias. Nombrá un camino que estés sopesando.",
    "traj.readonly":
      "El fit es una proyección sobre hipótesis ya selladas. Abrirlo no recalcula nada ni mueve ningún índice.",
    "traj.noPercentage": "Cuentas por requisito — nunca un porcentaje de destino.",
    "traj.select": "Trayectoria",
    "traj.addPlaceholder": "nombrá un camino que estés sopesando",
    "traj.add": "Agregar trayectoria",
    "traj.requirements": "Requisitos de capacidad",
    "traj.req.empty":
      "Todavía no hay requisitos. Agregá las capacidades que este camino exige — cada una respaldada por una hipótesis.",
    "traj.req.labelPlaceholder": "capacidad que este camino exige",
    "traj.req.hypothesis": "Respaldada por la hipótesis",
    "traj.req.add": "Agregar requisito",
    "traj.req.needHypothesis":
      "Agregá una hipótesis primero — un requisito tiene que estar respaldado por una.",
    "traj.req.allUsed":
      "Todas las hipótesis ya respaldan un requisito acá. Agregá una hipótesis nueva para sumar otro.",
    "traj.req.backedBy": "hipótesis #{id}",
    "fit.met": "Cumplido",
    "fit.supported": "Con respaldo",
    "fit.open": "Abierto",
    "fit.against": "En contra",
    "fit.discarded": "Descartado",
    "fit.total": "requisitos",
    "traj.disc.title": "¿Qué camino separa el próximo experimento?",
    "traj.disc.pickTwo": "Elegí dos trayectorias distintas para comparar.",
    "traj.disc.run": "Buscar la capacidad que discrimina",
    "traj.disc.suggested": "Capacidad más barata de testear ahora",
    "traj.disc.onlyIn": "la exige solo {name}",
    "traj.disc.shared": "{n} requisito(s) compartido(s) por las dos",
    "traj.disc.distinguishing": "Capacidades que distinguen",
    "traj.disc.none":
      "Ninguna capacidad abierta separa a estas dos en este momento.",
    "examples.trajectoryHint": "tocá para completar",
    "example.trajectory1": "Ingeniera de sistemas en equipos chicos y de alta confianza",
    "example.trajectory2": "Investigadora independiente / escritora técnica",

    // Control de Compass ID
    "user.button": "Compass ID",
    "user.title": "Tu Compass ID",
    "user.explainer":
      "Tu compass es privado para este ID. Guardalo para volver a este compass; no compartas nada que no quieras que quede vinculado.",
    "user.currentLabel": "ID actual",
    "user.copy": "Copiar",
    "user.copied": "Copiado",
    "user.setLabel": "Poné un ID propio",
    "user.setPlaceholder": "pegá un ID para cargar su compass",
    "user.apply": "Cargar compass",
    "user.new": "Compass nuevo",
    "user.invalid": "Usá 1 a 64 caracteres: letras, dígitos, guion o guion bajo.",
    "user.close": "Cerrar",
  },
} as const;

type Dict = typeof dict.en;
type Key = keyof Dict;

/** Substitute {name} placeholders with values. */
function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (m, k) =>
    k in vars ? String(vars[k]) : m,
  );
}

interface I18nContextType {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: Key, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  // Default language is English.
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    const stored = localStorage.getItem("compass-lang") as Lang | null;
    if (stored === "en" || stored === "es") {
      setLangState(stored);
    }
  }, []);

  const setLang = (newLang: Lang) => {
    setLangState(newLang);
    localStorage.setItem("compass-lang", newLang);
  };

  const t = (key: Key, vars?: Record<string, string | number>): string => {
    const template = dict[lang][key] ?? dict.en[key] ?? key;
    return interpolate(template, vars);
  };

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

/** Maps a Lang to the narrator's expected `language` query value. */
export function narratorLanguage(lang: Lang): "English" | "Spanish" {
  return lang === "es" ? "Spanish" : "English";
}

/**
 * Renders the localized "single next step" sentence on the FRONTEND from
 * next_step.kind (and its id/count fields), so it follows the UI language.
 * The backend's next_step.detail is used only as a fallback when the kind
 * is unknown.
 */
export function nextStepSentence(
  t: (key: Key, vars?: Record<string, string | number>) => string,
  next: NextStep,
): string {
  const kind = next.kind as NextStepKind;
  const id =
    (next.experiment_id as string | number | undefined) ??
    (next.hypothesis_id as string | number | undefined) ??
    "";
  const count = (next.count as number | undefined) ?? 0;

  switch (kind) {
    case "completar_experimento":
      return t("nextStep.completar_experimento", { id });
    case "ejecutar_experimento":
      return t("nextStep.ejecutar_experimento", { id });
    case "validar_evidencia":
      return t("nextStep.validar_evidencia", { count });
    // The kind carries a non-ASCII 'ñ'; the dict key is ASCII-safe.
    case "diseñar_experimento":
      return t("nextStep.disenar_experimento", { id });
    case "abstain":
      return t("nextStep.abstain");
    default:
      // Unknown kind: fall back to the backend-provided detail.
      return next.detail;
  }
}

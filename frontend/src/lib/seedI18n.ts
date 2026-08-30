// Presentation-layer localization of the demo-seed fixtures (seed_demo.py).
// These strings are sealed English in the audit chain and are NOT translated
// server-side; this map only affects display. Falls through unchanged for any
// string it doesn't know.

export const SEED_ES: Record<string, string> = {
  "Has systems-design capability: closes end-to-end architectures unaided, not just writes functions.":
    "Tiene capacidad de diseño de sistemas: cierra arquitecturas de punta a punta sin ayuda, no solo escribe funciones.",
  "The signal is explained by fast execution under a deadline, not by design: performs on someone else's scaffold, not designing her own.":
    "La señal se explica por ejecución rápida bajo plazo, no por diseño: rinde sobre el andamiaje de otro, no diseñando el propio.",
  "Systems architect on small, high-trust teams":
    "Arquitecta de sistemas en equipos chicos de alta confianza",
  "High-tempo delivery engineer": "Ingeniera de entrega de alto ritmo",
  "Owns an end-to-end architecture and defends it under critique.":
    "Es dueña de una arquitectura de punta a punta y la defiende bajo crítica.",
  "Ships fast inside a structure someone else designed.":
    "Entrega rápido dentro de una estructura que diseñó otro.",
  "Closes an end-to-end architecture unaided":
    "Cierra una arquitectura de punta a punta sin ayuda",
  "Sustains output without an external scaffold":
    "Sostiene la producción sin andamiaje externo",
  "Performs under deadline on an existing scaffold":
    "Rinde bajo plazo sobre un andamiaje existente",
  "I feel I understand whole systems, not just parts.":
    "Siento que entiendo sistemas enteros, no solo partes.",
  "Returned on her own to redesign the engine three nights in a row with no one asking.":
    "Volvió por su cuenta a rediseñar el motor tres noches seguidas sin que nadie se lo pidiera.",
  "Architecture PR accepted and merged by external maintainers (cel-go #1445).":
    "PR de arquitectura aceptado y mergeado por mantenedores externos (cel-go #1445).",
  "Design a new system's authority architecture from scratch (no external scaffold) and have a third party audit it.":
    "Diseñar desde cero la arquitectura de autoridad de un sistema nuevo (sin andamiaje externo) y que un tercero la audite.",
  "An independent reviewer confirms the architecture closes on its own and holds its invariants under critique.":
    "Un revisor independiente confirma que la arquitectura cierra por sí sola y sostiene sus invariantes bajo crítica.",
  "The design depends on structure provided by someone else, or collapses at the reviewer's first counter-example.":
    "El diseño depende de una estructura provista por otro, o colapsa ante el primer contraejemplo del revisor.",
};

/**
 * Presentation-only mapping of a known English seed string to Spanish. Any
 * string that is not a known seed fixture (user/LLM/O*NET content, already
 * authored in the active language) falls through unchanged.
 */
export function localizeSeed(
  text: string | null | undefined,
  locale: string,
): string {
  return locale === "es" && text && SEED_ES[text] ? SEED_ES[text] : (text ?? "");
}

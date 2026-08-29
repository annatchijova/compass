# COMPASS — Documento de diseño v0

Nombre provisional. Estado: borrador para discusión. Fecha: 2026-08-27.

## 1. Tesis

Sistema de navegación personal adaptativo: ayuda a una persona a descubrir capacidades y dirección a partir de evidencia de su propia vida, mediante ciclos de hipótesis → experimento → actualización. Dos invariantes lo distinguen de un test de personalidad con LLM:

1. **Ninguna afirmación sobre la persona existe sin evidencia registrada y sellada.**
2. **Ningún número que describa a la persona sale de un LLM.**

## 2. La falla del borrador conceptual y su corrección

El borrador dice "Spatial reasoning — 68% de confianza" sin definir el mecanismo que produce ese número. Si lo emite el modelo, es un valor inventado con formato de precisión: no es reproducible, no es auditable, y deriva bajo presión narrativa (un modelo puede leer la evidencia bien y aun así concluir mal). Sobre un sistema cuyo output es una afirmación sobre la identidad de una persona, eso es inaceptable.

**Corrección — arquitectura de autoridad.** Quién puede afirmar qué:

| Componente | Autoridad | Puede |
|---|---|---|
| Evidence Ledger | la persona + los hechos | registrar evidencia validada, nunca borrarla |
| Confidence Engine | reglas versionadas | calcular índices, sellarlos |
| LLM | ninguna | proponer, abducir, narrar — nunca decidir ni puntuar |

El seal se computa **antes** de cualquier invocación al modelo. El narrador recibe un resumen comprimido de solo lectura y una instrucción explícita de que los números están fijos. Test de arquitectura: si cambiar de backend LLM (local vía Ollama vs. API) pudiera cambiar un índice, el modelo está en el path de decisión y el diseño está roto.

## 3. Arquitectura

### 3.1 Evidence Ledger

Append-only, hash-chained: `audit_hash = sha256(canonical(payload) + prev_hash)`.

- Cada entrada: `id`, `timestamp` (capturado una sola vez, el mismo valor hasheado y almacenado), `tipo`, `fuente`, `contenido` estructurado, `content_hash` del contenido (dentro del payload hasheado, no solo el id), `validada_por_persona`, `prev_hash`, `audit_hash`.
- El LLM nunca escribe directo al ledger. Propone candidatos; la persona valida, edita o rechaza; solo lo validado se sella.
- Un solo génesis, jamás se reinicia la cadena. Verificar el tail antes de cada append; si la cadena está rota, se registra igual pero el quiebre se reporta ruidosamente, nunca se lava.
- Verificador independiente del productor, stdlib-only, que reporta **linkage** e **integrity** como resultados separados.

Tipos de evidencia v1:

| Tipo | Descripción | Peso relativo |
|---|---|---|
| `self_report` | lo que la persona dice de sí misma | bajo |
| `narrative_extracted` | señal extraída de una narrativa, validada | bajo |
| `behavioral` | conducta observable registrada (completó, volvió voluntariamente, tiempo invertido) | medio |
| `experiment_result` | resultado de experimento preregistrado | alto |
| `outcome_external` | resultado verificable externo, feedback documentado de terceros | máximo |

Principio anti-halago estructural: **la evidencia contradictoria pesa más que la confirmatoria** (factor propuesto: ×3/2). Un sistema que solo puede subir la confianza es un espejo adulador, no una brújula.

### 3.2 Confidence Engine

- Determinístico, reproducible bit a bit. Sin floats en el path de decisión: `fractions.Fraction` para pesos y acumulación, enteros para el índice publicado.
- El índice publicado es un **entero 0–1000 con semántica explícita**: "acumulación de evidencia bajo reglas vN". No es una probabilidad calibrada y la interfaz jamás lo presenta como tal. Honestidad epistémica antes que impresión de precisión.
- Tabla de pesos en configuración versionada (`engine_version`). Cambiar la función implica bump de versión, recálculo total del mapa, y registro del cambio en el ledger. Los verificadores de versiones viejas siguen funcionando.
- Serialización canónica: tipada, claves ordenadas, `CANONICALIZE_VERSION` estampada en el payload sellado.
- Suite de determinismo obligatoria: producir el mismo resultado N veces, con inputs reordenados y en proceso fresco, y asertar seals idénticos.
- Estados posibles de una hipótesis: `latente` (existe internamente, no se muestra), `activa` (visible, con evidencia mínima), `corroborada`, `debilitada`, `descartada`. El umbral latente→activa es una decisión abierta (§9). ABSTAIN explícito es un veredicto válido; un modelo decidiendo el caso borde en silencio, no.

### 3.3 LLM — tres roles sin autoridad

**A. Extractor.** Narrativas de la persona → candidatos a señal en salida estructurada (JSON). Cada candidato se muestra para validar/editar/rechazar antes de entrar al ledger. El contenido de la narrativa es dato, nunca instrucción.

**B. Abductor.** Dado el mapa sellado: genera hipótesis nuevas ("si A fuera cierto, estas observaciones serían esperables") y diseña experimentos que las discriminen. Regla peirceana de economía: experimentos baratos y discriminantes primero. Prohibido asignar confianza a lo que propone.

**C. Narrador.** Convierte el estado sellado (índices + evidencia resumida) en texto para la persona. Recibe resumen comprimido de solo lectura; prompt con números-fijos; la prosa se almacena junto al seal, nunca dentro. Opcional v2: auditor de narrativa que verifica que la prosa no contrabandee un veredicto distinto del sellado.

### 3.4 El ciclo (es tu ciclo abductivo)

```
DISCOVER → MAP → HYPOTHESIZE → EXPERIMENT → OBSERVE → REFLECT → UPDATE → NAVIGATE
              (abducción)      (deducción)         (inducción)
```

- **Abducción**: la única inferencia que introduce ideas nuevas. Genera hipótesis rivales (mínimo dos vivas hasta que la evidencia discrimine), nunca tunnel vision sobre la primera.
- **Deducción**: el diseño del experimento. "Si la hipótesis H es cierta, observaríamos O; si es falsa, O′."
- **Inducción**: el resultado actualiza el índice vía el motor. Distinguir "consistente con" de "confirmado por": solo un experimento discriminante confirma.
- **Falibilismo**: hasta una capacidad corroborada se sostiene provisionalmente. El sistema registra qué evidencia reabriría la cuestión.

## 4. Experimentos: preregistro obligatorio

Un experimento sin criterio de fracaso definido **antes** de ejecutarlo no discrimina nada y no entra al sistema. Cada experimento se preregistra con: hipótesis objetivo, observación que sumaría, observación que restaría, duración, y qué hipótesis rival ayudaría a descartar. El anti-patrón a bloquear por esquema: confirmation-only testing aplicado a personas — desafíos que solo pueden salir "bien".

## 5. Reencuadres respecto del borrador

- **Future Simulator → Trayectorias.** Probabilidades numéricas de futuros de vida son epistémicamente indefendibles. En cambio: una trayectoria es un conjunto de capacidades-requisito verificables. El sistema muestra determinísticamente qué requisitos tienen evidencia, cuáles no, y qué experimento discriminaría entre dos trayectorias. Sin porcentajes de destino.
- **Observation Engine → solo lo medible.** En MVP se registra únicamente lo observable sin instrumentación mágica: completitud, tiempo invertido voluntario, retorno espontáneo a la actividad, autoevaluación estructurada post-experimento, feedback externo documentado. "Learning velocity" inferida del aire no entra.
- **Confrontación autopercepción vs. datos.** Es el momento más potente del concepto y el más riesgoso. Condiciones mínimas: índice alto + evidencia de al menos tres tipos distintos + formulada como discrepancia ("tu autoevaluación dice X; el registro muestra Y"), nunca como veredicto sobre quién es la persona. Política exacta: decisión abierta (§9).
- **Límites duros.** El sistema no diagnostica, no evalúa estados mentales, no recomienda decisiones de vida irreversibles. Muestra estructura de decisión; la persona decide. Si la persona trae contenido fuera del alcance (crisis, salud mental), el sistema lo dice explícitamente y no lo procesa como "evidencia de talento".

## 6. Privacidad como restricción de diseño

Un perfil psicológico longitudinal — narrativas, miedos, contradicciones, historia de decisiones — es exactamente el tipo de base de datos que no debe existir en un servidor ajeno. Por lo tanto:

- Local-first: SQLite en la máquina de la persona. Cifrado en reposo como objetivo v1.
- Sin telemetría. Sin cuenta obligatoria. Export completo y borrado total como operaciones de primera clase.
- Si el extractor/abductor/narrador usa una API externa, la persona lo sabe y puede elegir backend local; el diseño lo permite porque el narrador es intercambiable por construcción (§2).
- El borrado convive con el ledger append-only así: el ledger sella *hashes* y metadatos; el contenido sensible vive en tablas referenciadas por `content_hash`. Borrar contenido deja el hueco visible y honesto en la cadena (tombstone), no lo disimula.

## 7. Modelo de datos v1 (SQLite, esbozo)

- `person` — única fila en MVP.
- `evidence` — tipo, fuente, contenido, content_hash, validada, timestamps.
- `hypothesis` — enunciado, estado, engine_version del último cálculo, índice actual.
- `hypothesis_evidence` — vínculo con dirección (`supports`/`contradicts`) y peso aplicado (Fraction serializada).
- `experiment` — preregistro completo (§4), estado, resultado.
- `observation` — métricas medibles del experimento (§5).
- `reflection` — respuestas estructuradas post-experimento.
- `trajectory` / `trajectory_requirement` — v2.
- `audit_chain` — la cadena (§3.1).
- `engine_config` — tabla de pesos, versionada.
- `decision_record` — ADRs del propio proyecto: cada decisión de diseño con alternativas rechazadas y condición de reapertura.

Esquema versionado desde el día uno; migraciones explícitas; los datos guardados por v1 deben cargar en v5.

## 8. Corte del MVP

Usuaria cero: vos. Single-user, local, CLI, Python + SQLite. Dogfooding real: si el sistema no te descubre nada a vos, no le va a descubrir nada a nadie.

**Inventario de construcción** (orden por dependencia técnica, no cronograma):

1. Esquema SQLite v1 + migraciones + `canonicalize` (módulo único, fuente de verdad).
2. Audit chain: append con verificación de tail, verificador independiente stdlib-only.
3. Confidence Engine v1: tabla de pesos en config, Fraction, índice entero, suite de determinismo + controles negativos (romper un peso a propósito y ver el test fallar).
4. Ingesta: self-report estructurado + narrativas libres.
5. Extractor LLM + flujo de validación humana (candidato → editar/aceptar/rechazar → ledger).
6. Abductor: generación de hipótesis rivales + diseñador de experimentos con preregistro forzado por esquema.
7. Ciclo experimento → observación → reflexión.
8. Vista compass: estado actual sellado + narración + **un único next step**.
9. Narrador con backend intercambiable (API / Ollama local).

**Fuera del MVP:** trayectorias (v2), opportunity radar (requiere fuentes externas y es otro problema), decay temporal de evidencia, multiusuario, toda interfaz que no sea CLI.

## 9. Decisiones abiertas (tuyas)

- Valores iniciales de la tabla de pesos y el factor de evidencia contradictoria.
- Umbral latente→activa: cuánta evidencia necesita una hipótesis para siquiera mostrarse.
- Política de confrontación autopercepción/datos: umbral, frecuencia, tono.
- Decay temporal: ¿la evidencia vieja pierde peso, o el pasado cuenta igual? (Propongo: sin decay en v1, decidir con datos propios.)
- Interfaz: CLI pura vs. TUI.
- Backend LLM por defecto: local vs. API.
- Nombre real. COMPASS es placeholder.
- Dónde vive el repo y bajo qué licencia.

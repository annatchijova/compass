# COMPASS

Sistema de navegación personal adaptativo. Nombre provisional.

Dos invariantes definen el proyecto: ninguna afirmación sobre la persona
existe sin evidencia registrada y sellada, y ningún número que la
describa sale de un LLM. El diseño completo, la arquitectura de
autoridad y las decisiones abiertas están en
`docs/COMPASS-DESIGN-v0.md`.

## Estado: esqueleto completo (módulos 1-9 del inventario, §8)

1. **Esquema SQLite v1 + migraciones** (`db.py`) — versionado desde el
   día uno, rechazo de esquemas futuros, constraints con dientes
   (preregistro y tombstone forzados por esquema).
2. **Cadena de auditoría** (`audit_chain.py`) — append-only,
   hash-chained, génesis único, cola verificada sin lavado, linkage e
   integrity separados.
3. **Confidence Engine v1** (`engine.py`) — pesos PROVISORIOS sellados
   en `engine_config` y registrados en `decision_record` con condición
   de reapertura; aritmética exacta con `Fraction`, índice entero
   0-1000 asintótico (la certeza total no existe), evidencia
   contradictoria con factor 3/2, corroboración solo con evidencia
   discriminante, `descartada` pegajosa (solo la persona).
4. **Dominio** (`domain.py`) — evidencia (candidatos vs. validada),
   tombstone honesto con razón declarada, hipótesis, y el ciclo
   completo experimento → observación → reflexión; completar un
   experimento genera la evidencia según el criterio PREREGISTRADO que
   se cumplió (inconcluso no genera nada: no discriminó).
5. **Vista compass** (`views.py`) — estado sellado, resumen comprimido
   de solo lectura, y UN siguiente paso por reglas determinísticas
   explícitas con ABSTAIN válido.
6. **Capa LLM** (`llm.py`) — tres roles sin autoridad (extractor,
   abductor, narrador); toda salida de modelo validada en frontera o
   rechazada; narrativa de la persona como dato, jamás instrucción;
   `FakeBackend` determinístico + esqueletos Anthropic/Ollama.
7. **CLI** (`cli.py`, `python -m compass`) — ciclo completo usable
   offline con el backend fake.

Core: stdlib pura. `pytest` solo para desarrollo.

## Correr

```
python3 -m pytest                       # 91 tests
PYTHONPATH=src python3 -m compass init  # y de ahí: person, hyp, evidence,
                                        # link, exp, recompute, compass...
python3 tools/verify_chain.py compass.db
```

`tools/verify_chain.py` es el verificador **independiente**: stdlib
pura, no importa el paquete. Reimplementa la spec a propósito, para que
confirmar la cadena no exija confiar en el código que la escribió.

## Spec del sobre sellado (para verificadores de terceros)

```
material   = json.dumps({"content_hashes": [...ordenado...], "cv": int,
                         "op": str, "payload_c14n": str, "seq": int,
                         "ts": str},
                        sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False)
audit_hash = sha256(utf8(material) + utf8(prev_hash))
génesis    : prev_hash = "0" * 64, seq = 1, único para siempre
```

`payload_c14n` se persiste como el string canónico exacto que se hasheó;
`content_hashes` sella el contenido referenciado
(`sha256(utf8(evidence.content))`): editar la fila referenciada se
detecta aunque la cadena recompute bien.

## Orden inviolable de la narración

```
estado -> seal -> resumen comprimido -> narrador -> prosa junto al seal
```

El seal existe antes de que cualquier modelo hable; el narrador recibe
un resumen de solo lectura con el seal adentro; la prosa se registra en
la cadena por su hash, nunca dentro del seal. Test arquitectónico:
cambiar de backend cambia la prosa y ningún número
(`test_backend_intercambiable_no_cambia_numeros`).

## Integridad de la suite

- Red-first: cada control negativo adultera la base de verdad y aserta
  la detección.
- Mutaciones ejecutadas y atrapadas (7): quitar `prev_hash` del cómputo
  (atrapada por el verificador EXTERNO — el interno queda en tautología
  con el productor mutado); colapsar bool en int; aceptar esquemas
  futuros; contar evidencia sin validar; quitar el factor anti-halago;
  sellado tardío (el narrador deja de recibir el seal); inversión de
  prioridad en las reglas del next step.
- Oráculos exactos del engine calculados A MANO desde la fórmula, más
  invariante metamórfico: permutar el orden de carga no cambia el índice.
- Determinismo verificado entre procesos frescos con `PYTHONHASHSEED`
  distinto; recompute doble produce el mismo seal bit a bit.

**Puntos ciegos declarados** (lo que esta suite NO cubre):
- `AnthropicBackend` y `OllamaBackend` NO fueron probados en vivo: el
  contrato está testeado vía fake; la primera corrida real puede
  encontrar diferencias de forma de respuesta.
- Los prompts (extractor/abductor/narrador) son v0 sin evaluación
  adversaria: un modelo capturado por una narrativa persuasiva puede
  proponer candidatos sesgados — la mitigación estructural es que nada
  entra al ledger sin validación de la persona y ningún número sale del
  modelo, pero la calidad de las propuestas no está medida.
- Concurrencia real multiproceso más allá de `BEGIN IMMEDIATE` + WAL +
  busy_timeout; recuperación tras kill -9 a mitad de transacción (se
  confía en SQLite); rendimiento con cadenas largas.
- Un adversario con escritura total puede reescribir la historia desde
  el génesis: la cadena hace el tamperizado detectable ante un
  verificador con una copia previa del hash de cola, no imposible.
  Anclar periódicamente ese hash fuera de la máquina queda como
  decisión abierta.

## Decisiones abiertas (design doc §9)

Los valores del engine v1 son PROVISORIOS: puestos para desbloquear el
esqueleto, registrados en `decision_record` #1 con condición de
reapertura explícita (auditoría con datos reales). Igual de abiertos:
política de decay, política de confrontación autopercepción/datos,
anclaje externo del hash de cola, nombre real, licencia.

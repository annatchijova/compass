# COMPASS — léeme

Explicación del repo escrita por Claude como **ejercicio de comprensión**: la
prueba no es si el resumen suena bien, es si un lector externo entiende el
proyecto leyendo el código y la documentación. Lo que sigue salió de leer el
repo, no de parafrasear el README.

Al final está la parte que importa: **qué no se entendió solo**.

- Fecha: 2026-08-30 · commit `c263630` · rama `claude/readme-outdated-5wehvt`
- Provenance: cada punto de "qué no se entendió solo" viene de un choque
  concreto durante una sesión de trabajo sobre este repo, no de una
  impresión general. Está anotado cuál en cada caso.

---

## Qué es, en una frase

Un test vocacional construido al revés del habitual: en vez de pedirte que te
autoevalúes y devolverte un perfil, trata "a qué me dedico" como un **ajuste
entre capacidades que demostraste y lo que un camino exige**, y te manda a
averiguarlo con experimentos.

## El problema del que sale

Las herramientas de orientación vocacional emiten números con cara de
precisión — "razonamiento espacial: 68%" — que no salen de ningún mecanismo
defendible. Si ese número lo produjo un modelo de lenguaje, es un valor
inventado disfrazado de medición: no es reproducible, no es auditable, y se
mueve según cómo le contaste tu historia. Sobre un sistema cuyo output es una
afirmación sobre la identidad de alguien, eso es inaceptable.

## La apuesta central

Dos invariantes, y todo lo demás se deriva de ahí:

1. Ninguna afirmación sobre la persona existe sin evidencia registrada y
   sellada.
2. Ningún número que describa a la persona sale de un LLM.

La segunda es la interesante, porque no se cumple pidiéndole al modelo que se
porte bien. Se cumple **por construcción**: el motor determinístico calcula y
*sella* cada índice antes de que se invoque a ningún modelo. El narrador
recibe un estado ya fijo. No puede mover un número que ya está sellado — no
porque no quiera, sino porque llega tarde.

Hay un test que *es* la tesis: cambiás el backend de Gemini al offline y solo
cambian las palabras, nunca un veredicto ni un sello
(`test_swapping_narrator_backend_never_changes_the_seal`).

## Cómo funciona el ciclo

Es abducción, en el sentido de Peirce, hecha producto:

- Contás algo de tu vida -> el **extractor** propone señales candidatas. No
  cuentan hasta que vos las validás.
- El **abductor** propone hipótesis RIVALES sobre una capacidad — mínimo dos
  vivas, para no hacer tunnel vision sobre la primera.
- Se diseña un **experimento discriminante**, con el criterio de fracaso
  escrito *antes* de correrlo. Un experimento que solo puede salir bien no
  discrimina nada, y el esquema lo bloquea.
- Lo corrés en tu vida real, registrás el resultado, el motor recalcula y
  vuelve a sellar.

Sobre eso van las **trayectorias**: un camino es un conjunto de
capacidades-requisito, cada una respaldada por una hipótesis. El fit se
muestra en cuentas — cumplido / con respaldo / abierto / en contra /
descartado — nunca un porcentaje de destino. Y `traj discriminate` te dice
cuál capacidad abierta conviene testear para separar dos caminos: economía de
investigación, la más barata primero.

## Las dos decisiones que le dan carácter

**La evidencia que contradice pesa más que la que confirma** (x3/2). Un
sistema que solo puede subir la confianza es un espejo halagador, no una
brújula. Es la diferencia entre esto y un horóscopo con dashboard.

**Corroborar exige un experimento discriminante.** Ningún volumen de
auto-reporte corrobora una hipótesis. Podés estar convencidísimo de algo:
sube el índice un poco y se queda ahí.

## La ingeniería que sostiene todo

- **Nada de float en el camino de decisión.** `Fraction` para todo peso y
  acumulación; el índice es un entero 0-1000 con piso asintótico — la certeza
  total no existe.
- **Ledger append-only, hash-encadenado**, con verificador independiente
  (`tools/verify_chain.py`) que reimplementa la especificación a propósito,
  para que confirmar la cadena no requiera confiar en el código que la
  escribió.
- **Tres señales separadas, nunca colapsadas en un booleano**: linkage,
  integrity y contenido. Borrar deja una lápida visible, no un hueco
  silencioso.
- **El determinismo se prueba, no se afirma**: mismo input, mismo sello bit a
  bit, entre procesos con distinto `PYTHONHASHSEED`.

## Dónde vive el LLM

Cinco roles que proponen, más el narrador; ninguno decide:

| Rol                     | Propone                                      |
|-------------------------|----------------------------------------------|
| Extractor               | señales candidatas desde una narrativa       |
| Abductor                | hipótesis rivales                            |
| Proponedor de trayectorias | caminos, SOLO con hipótesis que ya existen |
| Diseñador de experimentos | experimento discriminante + criterio de fracaso |
| Buscador de recursos    | dónde ir a ejecutar el experimento           |
| Narrador                | pone en palabras un estado YA sellado        |

El agente ADK tiene exactamente la autoridad de su tool set — y
`link_evidence` fue *quitado* deliberadamente, porque elegir qué evidencia se
vincula a qué hipótesis ya es un acto de puntuación.

La confrontación autopercepción-vs-datos es el caso extremo: ahí no participa
ningún modelo, ni decidiendo ni redactando. El motor devuelve cuentas y la
frase sale de plantilla fija.

## Mapa del repo

    src/compass/
      canonicalize.py   serialización canónica tipada (bool antes que int)
      db.py             esquema, migraciones, atomic()
      audit_chain.py    cadena hash-encadenada + verify_chain / verify_content
      engine.py         Confidence Engine v1: Fraction, índice 0-1000, sella
      domain.py         ops de dominio: evidencia, hipótesis, experimentos
      views.py          estado sellado + un único siguiente paso
      trajectories.py   fit vocacional (cuentas, sin porcentaje de destino)
      confrontation.py  autopercepción vs datos (política PROVISORIA v0)
      llm.py            roles sin autoridad + backends (Gemini/demo/fake/...)
      api.py            FastAPI sobre el dominio sellado
      cli.py            ciclo completo offline
      agent/agent.py    agente ADK, acotado por su tool set
    tools/verify_chain.py   verificador independiente, stdlib puro
    frontend/               Next.js, bilingüe EN/ES
    docs/                   diseño, arquitectura, red team, atribuciones

Escala: ~4500 líneas de Python, 162 tests, ~1500 líneas de documentación.

---

# Qué NO se entendió solo

Esto es lo que el repo no logra comunicar por sí mismo. Cada punto viene de
un choque real, no de una impresión.

### 1. Hay dos sellos distintos y ningún documento lo dice

`/api/state` y `/api/recompute` sellan materiales diferentes y devuelven
hashes distintos. Escribí un test comparando uno contra otro; falló, y tardé
en darme cuenta de que el error era mío y no del código. Alguien va a repetir
ese error. Merece una línea en el README o en `views.py`.

### 2. Las hipótesis latentes son invisibles en el estado sellado

Está justificado (design doc §3.2: una hipótesis sin evidencia mínima no
existe públicamente) pero vive en un docstring de `views.compass_state`, no
en el README. Generó un bug real: el selector de requisitos de una
trayectoria se alimentaba del estado sellado, así que no ofrecía capacidades
nuevas — justo las que el ciclo de experimentos apunta a resolver.

### 3. El README vende, el design doc explica — y están en idiomas distintos

`README.md` en inglés, `docs/COMPASS-DESIGN-v0.md` en español. El *porqué* de
casi todas las decisiones está en el segundo. Quien lea solo el primero se
lleva la tesis pero no el razonamiento.

### 4. El código habla español y la documentación inglés

Docstrings, mensajes de error y salida del CLI en español; README,
ARCHITECTURE y contenido de producto en inglés. Uno se acostumbra, pero el
primer rato desorienta y no está explicado en ningún lado.

---

## Lo que sí se entiende de una

La tesis. "Una brújula, no un espejo" y "ningún número sale del modelo" se
agarran en el primer párrafo y no se sueltan.

Y una observación sobre la forma: ~1500 líneas de documentación para ~4500 de
código, con 162 tests. Ese no es un ratio de hackathon, es un ratio de
proyecto que quiere ser auditado. La sección de puntos ciegos declarados hace
más por la credibilidad que cualquier claim del README — es raro y es lo mejor
que tiene.

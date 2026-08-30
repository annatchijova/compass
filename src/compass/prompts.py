"""Guía de narrativa: andamiaje para que nadie se trabe frente a una caja en
blanco — y menos una persona neurodivergente.

Una caja que dice "contá algo de tu vida" es una trampa de función ejecutiva:
demasiado abierta, demasiado abstracta, sin punto de entrada. La guía la
reemplaza por preguntas CONCRETAS y EPISÓDICAS ("una vez que…", "un momento
en que…"), de a una, chiquitas, sin presión y con permiso explícito de
saltear. Cada pregunta apunta a hacer aflorar una señal de capacidad o
interés SIN pedir introspección abstracta.

Principios (accesibilidad primero):
- Episódico, no rasgo: "una vez que perdiste la noción del tiempo", no
  "¿sos una persona enfocada?".
- Una a la vez: nada de muros de preguntas.
- Concreto y pequeño: se responde con una anécdota, no con un ensayo.
- Sin juicio ni presión: saltear es válido; no hay respuesta correcta.

El banco es estático y versionado (PROMPTS_VERSION); las respuestas van al
extractor, que propone señales que la persona valida. La guía no concluye ni
puntúa nada — solo desbloquea la página en blanco. La capa adaptativa (el rol
Reflector en llm.py) propone la SIGUIENTE pregunta según lo ya dicho.
"""

from __future__ import annotations

PROMPTS_VERSION = 1

# Dos niveles. "easy": puerta de entrada suave — cortas, tibias, se responden
# en pocas palabras, para no abrumar (arranque, o alguien saturado). "deeper":
# episódicas y más evocativas, para cuando ya hay confianza. La UI muestra las
# fáciles primero; las profundas quedan disponibles, nunca forzadas.
# (code, tier, text_en, text_es)
STARTER_PROMPTS = [
    # --- easy (low activation) ---
    ("like", "easy", "What do you like doing?", "¿Qué te gusta hacer?"),
    ("free_time", "easy", "When you get to choose, where does your time go?",
     "Cuando podés elegir, ¿en qué se te va el tiempo?"),
    ("came_easy", "easy", "What subject or topic came easy to you?",
     "¿Qué materia o tema te resultaba fácil?"),
    ("people_ask", "easy", "What do people often ask you to help with?",
     "¿Con qué te suelen pedir ayuda?"),
    ("as_a_kid", "easy", "What did you love doing as a kid?",
     "¿Qué te encantaba hacer de chica?"),
    ("free_saturday", "easy", "A free Saturday, nothing you have to do — what "
     "would you do?",
     "Un sábado libre, sin nada obligatorio: ¿qué harías?"),
    ("without_effort", "easy", "What comes out well for you without much effort?",
     "¿Qué te sale bien sin esforzarte mucho?"),
    ("curious", "easy", "What are you curious about lately?",
     "¿Qué te da curiosidad últimamente?"),
    # --- deeper (episodic) ---
    ("flow", "deeper", "Think of a time you lost track of hours doing "
     "something. What were you doing?",
     "Pensá en una vez que perdiste la noción del tiempo haciendo algo. ¿Qué "
     "estabas haciendo?"),
    ("easy_to_you", "deeper", "Has someone ever thanked you for something that "
     "felt easy to you? What was it?",
     "¿Alguna vez alguien te agradeció por algo que a vos te resultó fácil? "
     "¿Qué era?"),
    ("fixed_it", "deeper", "Tell me about something you fixed or figured out "
     "that others found hard.",
     "Contame algo que arreglaste o resolviste que a otros les costaba."),
    ("came_back", "deeper", "What did you go back to, more than once, without "
     "anyone asking you to?",
     "¿Qué volviste a hacer, varias veces, sin que nadie te lo pidiera?"),
    ("couldnt_drop", "deeper", "Think of something that frustrated you so much "
     "you couldn't drop it until you understood it.",
     "Pensá en algo que te frustró tanto que no pudiste soltarlo hasta "
     "entenderlo."),
    ("your_way", "deeper", "Is there something you do differently from most "
     "people, even if they say it's 'wrong'?",
     "¿Hay algo que hacés distinto de la mayoría, aunque te digan que está "
     "'mal'?"),
    ("most_yourself", "deeper", "When did you feel most like yourself while "
     "working on something? What was it?",
     "¿Cuándo te sentiste más vos misma trabajando en algo? ¿Qué era?"),
    ("helped_natural", "deeper", "Tell me about a time you helped someone and "
     "it came out naturally.",
     "Contame una vez que ayudaste a alguien y te salió natural."),
    ("lost_you", "deeper", "What's something you tried that just wasn't for "
     "you — and what specifically didn't fit?",
     "¿Qué probaste que simplemente no era para vos? ¿Qué, en concreto, no "
     "encajaba?"),
    ("small_win", "deeper", "What's a small thing you did this week that felt "
     "good to get right?",
     "¿Qué cosa chica hiciste esta semana que se sintió bien hacer bien?"),
]

TIERS = ("easy", "deeper")


def starter_prompts(lang: str = "en", tier: str | None = None) -> list[dict]:
    """Las preguntas-guía en el idioma pedido, con su nivel (easy|deeper). La
    persona elige UNA, la responde, y su respuesta va al extractor. `tier`
    opcional filtra por nivel; sin él, vienen todas (las fáciles primero)."""
    idx = 3 if lang == "es" else 2
    return [{"code": p[0], "tier": p[1], "text": p[idx]}
            for p in STARTER_PROMPTS
            if tier is None or p[1] == tier]

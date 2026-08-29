"""CLI de COMPASS. Esqueleto usable: init, dominio, recompute, compass.

Base de datos: --db, o COMPASS_DB, o ./compass.db.
Backend LLM para --narrar: COMPASS_BACKEND=fake|anthropic|ollama (fake
por defecto: funciona offline y no puede tocar ningún número por
construcción).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import domain, engine, views
from .audit_chain import verify_chain
from .db import open_db
from .llm import Narrator, backend_from_env


def _db_path(args) -> str:
    return args.db or os.environ.get("COMPASS_DB", "compass.db")


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_init(args):
    conn = open_db(_db_path(args))
    chash = engine.seed_default_config(conn)
    print(f"base lista: {_db_path(args)}")
    print(f"engine v1 activado (config_hash={chash})")
    print("recordá: los pesos son PROVISORIOS; el decision_record #1 "
          "registra la condición de reapertura")


def cmd_person(args):
    conn = open_db(_db_path(args))
    domain.person_set(conn, args.nombre)
    print(f"persona: {args.nombre}")


def cmd_evidence_add(args):
    conn = open_db(_db_path(args))
    try:
        content = json.loads(args.contenido)
    except json.JSONDecodeError:
        content = {"texto": args.contenido}
    eid = domain.evidence_add(
        conn, evidence_type=args.tipo, source=args.fuente,
        content=content, validated=not args.sin_validar,
    )
    print(f"evidencia #{eid} registrada"
          + (" (pendiente de validación)" if args.sin_validar else ""))


def cmd_evidence_validate(args):
    conn = open_db(_db_path(args))
    domain.evidence_validate(conn, args.id)
    print(f"evidencia #{args.id} validada")


def cmd_evidence_forget(args):
    conn = open_db(_db_path(args))
    domain.evidence_tombstone(conn, args.id, args.razon)
    print(f"evidencia #{args.id} borrada (tombstone declarado en la cadena)")


def cmd_hyp_add(args):
    conn = open_db(_db_path(args))
    hid = domain.hypothesis_add(conn, statement=args.statement, origin="person")
    print(f"hipótesis #{hid} registrada (latente hasta que la evidencia diga otra cosa)")


def cmd_hyp_discard(args):
    conn = open_db(_db_path(args))
    domain.hypothesis_discard(conn, args.id, args.razon)
    print(f"hipótesis #{args.id} descartada (solo vos podés reactivarla)")


def cmd_hyp_reactivate(args):
    conn = open_db(_db_path(args))
    domain.hypothesis_reactivate(conn, args.id)
    print(f"hipótesis #{args.id} reactivada como latente")


def cmd_link(args):
    conn = open_db(_db_path(args))
    domain.evidence_link(conn, hypothesis_id=args.hipotesis,
                         evidence_id=args.evidencia, direction=args.direccion)
    print(f"evidencia #{args.evidencia} -> hipótesis #{args.hipotesis} "
          f"({args.direccion})")


def cmd_exp_add(args):
    conn = open_db(_db_path(args))
    xid = domain.experiment_preregister(
        conn, hypothesis_id=args.hipotesis, design=args.diseno,
        success_criterion=args.exito, failure_criterion=args.fracaso,
        rival_hypothesis_id=args.rival, duration=args.duracion,
    )
    print(f"experimento #{xid} preregistrado")


def cmd_exp_start(args):
    conn = open_db(_db_path(args))
    domain.experiment_start(conn, args.id)
    print(f"experimento #{args.id} en curso")


def cmd_exp_complete(args):
    conn = open_db(_db_path(args))
    eid = domain.experiment_complete(conn, experiment_id=args.id,
                                     outcome=args.outcome, notes=args.notas)
    if eid is None:
        print(f"experimento #{args.id} completado: inconcluso, no discriminó "
              "(no genera evidencia)")
    else:
        print(f"experimento #{args.id} completado: generó evidencia #{eid}")
    print("corré 'recompute' para actualizar los índices")


def cmd_exp_abandon(args):
    conn = open_db(_db_path(args))
    domain.experiment_abandon(conn, args.id, args.razon)
    print(f"experimento #{args.id} abandonado")


def cmd_observe(args):
    conn = open_db(_db_path(args))
    domain.observation_add(conn, experiment_id=args.id, metric=args.metrica,
                           value=args.valor)
    print("observación registrada")


def cmd_reflect(args):
    conn = open_db(_db_path(args))
    domain.reflection_add(conn, experiment_id=args.id, question=args.pregunta,
                          answer=args.respuesta)
    print("reflexión registrada")


def cmd_recompute(args):
    conn = open_db(_db_path(args))
    result = engine.recompute_all(conn)
    print(f"recompute sellado: {result['seal']}")
    for r in result["results"]:
        print(f"  hipótesis #{r['hypothesis_id']}: índice {r['index']}/1000 "
              f"[{r['status']}]")


def cmd_compass(args):
    conn = open_db(_db_path(args))
    if args.narrar:
        out = views.narrate_compass(conn, Narrator(backend_from_env()))
        print(out["prose"])
        print(f"\n[estado sellado: {out['seal']}]")
    else:
        sealed = views.sealed_state(conn)
        _print(sealed["state"])
        print(f"\n[seal: {sealed['seal']}]")


def cmd_verify(args):
    conn = open_db(_db_path(args))
    report = verify_chain(conn)
    print(f"linkage_ok   : {report.linkage_ok}")
    print(f"integrity_ok : {report.integrity_ok}")
    for issue in report.issues:
        print(f"  [seq {issue['seq']}] {issue['kind']}: {issue['detail']}")
    print("(el verificador independiente vive en tools/verify_chain.py "
          "y no confía en este código)")
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="compass",
                                description="COMPASS: navegación personal con "
                                            "evidencia sellada")
    p.add_argument("--db", help="ruta de la base (default: $COMPASS_DB o ./compass.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="crear la base y activar el engine v1").set_defaults(fn=cmd_init)

    sp = sub.add_parser("person", help="fijar tu nombre")
    sp.add_argument("nombre")
    sp.set_defaults(fn=cmd_person)

    ev = sub.add_parser("evidence", help="evidencia").add_subparsers(required=True)
    e1 = ev.add_parser("add")
    e1.add_argument("--tipo", required=True)
    e1.add_argument("--fuente", required=True)
    e1.add_argument("--contenido", required=True,
                    help="JSON, o texto libre (se guarda como {\"texto\": ...})")
    e1.add_argument("--sin-validar", action="store_true",
                    help="registrar como candidato pendiente de validación")
    e1.set_defaults(fn=cmd_evidence_add)
    e2 = ev.add_parser("validate")
    e2.add_argument("id", type=int)
    e2.set_defaults(fn=cmd_evidence_validate)
    e3 = ev.add_parser("forget")
    e3.add_argument("id", type=int)
    e3.add_argument("--razon", required=True)
    e3.set_defaults(fn=cmd_evidence_forget)

    hy = sub.add_parser("hyp", help="hipótesis").add_subparsers(required=True)
    h1 = hy.add_parser("add")
    h1.add_argument("statement")
    h1.set_defaults(fn=cmd_hyp_add)
    h2 = hy.add_parser("discard")
    h2.add_argument("id", type=int)
    h2.add_argument("--razon", required=True)
    h2.set_defaults(fn=cmd_hyp_discard)
    h3 = hy.add_parser("reactivate")
    h3.add_argument("id", type=int)
    h3.set_defaults(fn=cmd_hyp_reactivate)

    ln = sub.add_parser("link", help="vincular evidencia a hipótesis")
    ln.add_argument("--hipotesis", type=int, required=True)
    ln.add_argument("--evidencia", type=int, required=True)
    ln.add_argument("--direccion", choices=("supports", "contradicts"),
                    required=True)
    ln.set_defaults(fn=cmd_link)

    ex = sub.add_parser("exp", help="experimentos").add_subparsers(required=True)
    x1 = ex.add_parser("add")
    x1.add_argument("--hipotesis", type=int, required=True)
    x1.add_argument("--diseno", required=True)
    x1.add_argument("--exito", required=True, help="criterio de éxito preregistrado")
    x1.add_argument("--fracaso", required=True, help="criterio de fracaso preregistrado")
    x1.add_argument("--rival", type=int)
    x1.add_argument("--duracion")
    x1.set_defaults(fn=cmd_exp_add)
    x2 = ex.add_parser("start")
    x2.add_argument("id", type=int)
    x2.set_defaults(fn=cmd_exp_start)
    x3 = ex.add_parser("complete")
    x3.add_argument("id", type=int)
    x3.add_argument("--outcome", choices=domain.OUTCOMES, required=True)
    x3.add_argument("--notas", default="")
    x3.set_defaults(fn=cmd_exp_complete)
    x4 = ex.add_parser("abandon")
    x4.add_argument("id", type=int)
    x4.add_argument("--razon", required=True)
    x4.set_defaults(fn=cmd_exp_abandon)

    ob = sub.add_parser("observe", help="registrar observación medible")
    ob.add_argument("id", type=int)
    ob.add_argument("--metrica", required=True)
    ob.add_argument("--valor", required=True)
    ob.set_defaults(fn=cmd_observe)

    rf = sub.add_parser("reflect", help="registrar reflexión post-experimento")
    rf.add_argument("id", type=int)
    rf.add_argument("--pregunta", required=True)
    rf.add_argument("--respuesta", required=True)
    rf.set_defaults(fn=cmd_reflect)

    sub.add_parser("recompute",
                   help="recalcular todos los índices y sellar").set_defaults(fn=cmd_recompute)

    cp = sub.add_parser("compass", help="estado actual + un único siguiente paso")
    cp.add_argument("--narrar", action="store_true",
                    help="narrar con el backend de COMPASS_BACKEND (fake por defecto)")
    cp.set_defaults(fn=cmd_compass)

    sub.add_parser("verify",
                   help="verificar la cadena (verificador interno)").set_defaults(fn=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rc = args.fn(args)
    except Exception as exc:  # frontera de la CLI: error claro, exit != 0
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return rc or 0


if __name__ == "__main__":
    raise SystemExit(main())

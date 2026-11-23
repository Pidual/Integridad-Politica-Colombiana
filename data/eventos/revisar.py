"""Revisión editorial de la bitácora de integridad.

    python data/eventos/revisar.py                      # lista los pendientes
    python data/eventos/revisar.py --ver ID             # muestra un evento con sus fuentes
    python data/eventos/revisar.py --aprobar ID --por "Nombre"
    python data/eventos/revisar.py --rechazar ID --por "Nombre" --motivo "texto"

Aprobar = una persona abrió las fuentes y confirmó que el resumen, el nivel y el estado
procesal corresponden a lo publicado. Solo los eventos aprobados salen en el sitio
(python -m data.build --solo-revisados). Rechazar marca el evento y no lo borra.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

PATH = Path(__file__).with_name("eventos.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver")
    ap.add_argument("--aprobar")
    ap.add_argument("--rechazar")
    ap.add_argument("--por", help="quién revisa")
    ap.add_argument("--motivo", default="")
    a = ap.parse_args()
    db = json.loads(PATH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in db["eventos"]}

    if a.ver:
        print(json.dumps(by_id[a.ver], ensure_ascii=False, indent=2))
        return
    target = a.aprobar or a.rechazar
    if target:
        if not a.por:
            raise SystemExit("Indica quién revisa con --por")
        e = by_id[target]
        e["revisado"] = bool(a.aprobar)
        e["rechazado"] = bool(a.rechazar)
        e["revision"] = {"por": a.por, "fecha": dt.date.today().isoformat(), "motivo": a.motivo}
        PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        print(("APROBADO " if a.aprobar else "RECHAZADO ") + target)
        return

    pend = [e for e in db["eventos"] if not e.get("revisado") and not e.get("rechazado")]
    print(f"{len(pend)} pendientes de {len(db['eventos'])}:")
    for e in pend:
        signo = "+" if e.get("positivo") else "-"
        print(f"  {signo} {e['id']:<45} {e['persona']:<38} {e['titulo'][:70]}")


if __name__ == "__main__":
    main()

"""Agrega o actualiza eventos en data/eventos/eventos.json desde un archivo JSON (lista de eventos).

    python data/eventos/agregar.py lote.json

Reglas (ver _doc en eventos.json): un evento por hecho, redacción neutral, al menos una
fuente con URL, nivel y estado obligatorios. Los eventos nuevos entran con revisado=false.
"""
import datetime as dt
import json
import sys
from pathlib import Path

PATH = Path(__file__).with_name("eventos.json")
REQUIRED = ("id", "persona", "rol", "estado", "titulo", "resumen", "fuentes")
ESTADOS = {"verificado", "sin_proceso", "preliminar", "abierto", "condena_no_firme", "en_firme", "archivado", "absuelto", "revocado", "desmentido"}


def main(src: str) -> None:
    db = json.loads(PATH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in db["eventos"]}
    new = json.loads(Path(src).read_text(encoding="utf-8"))
    for e in new:
        missing = [k for k in REQUIRED if not e.get(k)]
        if e.get("positivo") and e.get("tipo_positivo") not in ("P1", "P2", "P3"):
            missing.append("tipo_positivo (P1|P2|P3)")
        if not e.get("positivo") and not e.get("nivel"):
            missing.append("nivel")
        if missing:
            raise SystemExit(f"{e.get('id')}: faltan {missing}")
        if e["estado"] not in ESTADOS:
            raise SystemExit(f"{e['id']}: estado inválido {e['estado']}")
        if not all(f.get("url", "").startswith("http") for f in e["fuentes"]):
            raise SystemExit(f"{e['id']}: cada fuente necesita url")
        e.setdefault("revisado", False)
        e.setdefault("agregado", dt.date.today().isoformat())
        e.setdefault("rectificaciones", [])
        e.setdefault("respuesta", "")
        by_id[e["id"]] = {**by_id.get(e["id"], {}), **e}
    db["eventos"] = sorted(by_id.values(), key=lambda x: (x["persona"], x.get("fecha", "")))
    PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(new)} eventos procesados; total {len(db['eventos'])}")


if __name__ == "__main__":
    main(sys.argv[1])
